import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.imports.detection import normalize_column


def validate_file_magic_bytes(file_path: str, filename: str) -> bool:
    """Validate file binary signature (magic bytes) matches its declared extension."""
    fp = Path(file_path)
    if not fp.exists() or fp.stat().st_size == 0:
        return False

    with open(fp, "rb") as f:
        header = f.read(8)

    ext = filename.lower().split(".")[-1]
    if ext == "xlsx":
        return header.startswith(b"PK\x03\x04")
    elif ext == "xls":
        return header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    elif ext == "csv":
        # Reject executable / binary signatures (e.g., ELF, PE, ZIP, PDF)
        if header.startswith((b"MZ", b"\x7fELF", b"PK\x03\x04", b"%PDF", b"\xd0\xcf\x11\xe0")):
            return False
        # Verify text sample is valid printable ASCII/UTF-8
        try:
            sample = header.decode("utf-8", errors="strict")
            return not any(ord(c) < 9 or (13 < ord(c) < 32) for c in sample)
        except UnicodeDecodeError:
            return False
    return False


def sanitize_csv_formula_cell(value: Any) -> Any:
    """Neutralize CSV formula injection by prefixing '=', '+', '-', '@' with a single quote."""
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
            return f"'{value}"
    return value


def _get_mapped_value(row: dict[str, Any], mappings: dict[str, str], field: str, default: Any = None) -> Any:
    source_col = mappings.get(field)
    if source_col and source_col in row:
        val = row[source_col]
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            return val
    # Fallback: check if target field itself exists directly as column in row
    if field in row:
        val = row[field]
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            return val
    # Fallback: check normalized column names
    norm_field = normalize_column(field)
    for col_name, val in row.items():
        if normalize_column(col_name) == norm_field:
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                return val
    return default



def _parse_date(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return pd.to_datetime(value, utc=True).to_pydatetime()
    except Exception:
        return None


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: Any, default: int = 0) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def validate_dataframe(
    df: pd.DataFrame,
    dataset_type: str,
    mappings: dict[str, str],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    valid_count = 0
    warning_count = 0
    error_count = 0

    id_field = {
        "orders": "order_id",
        "products": "sku",
        "customers": "email",
    }.get(dataset_type)

    seen_ids: set[str] = set()

    for idx, row in df.iterrows():
        row_dict = {str(k): row[k] for k in df.columns}
        row_issues: list[dict[str, Any]] = []

        if dataset_type == "orders":
            if not _parse_date(_get_mapped_value(row_dict, mappings, "order_date")):
                row_issues.append({"type": "error", "field": "order_date", "message": "Invalid or missing order date"})
            total = _parse_float(_get_mapped_value(row_dict, mappings, "total_amount"))
            if total < 0:
                row_issues.append({"type": "error", "field": "total_amount", "message": "Negative total amount"})

        if dataset_type == "products":
            price = _parse_float(_get_mapped_value(row_dict, mappings, "price"))
            if price < 0:
                row_issues.append({"type": "error", "field": "price", "message": "Negative price"})
            if not _get_mapped_value(row_dict, mappings, "name"):
                row_issues.append({"type": "error", "field": "name", "message": "Missing product name"})

        if dataset_type == "inventory":
            stock = _parse_int(_get_mapped_value(row_dict, mappings, "stock_quantity"))
            if stock < 0:
                row_issues.append({"type": "warning", "field": "stock_quantity", "message": "Negative stock quantity"})

        if id_field and id_field in mappings:
            record_id = str(_get_mapped_value(row_dict, mappings, id_field, ""))
            if record_id:
                if record_id in seen_ids:
                    row_issues.append({"type": "warning", "field": id_field, "message": f"Duplicate {id_field}: {record_id}"})
                seen_ids.add(record_id)

        if any(i["type"] == "error" for i in row_issues):
            error_count += 1
        elif row_issues:
            warning_count += 1
        else:
            valid_count += 1

        if row_issues:
            issues.append({"row": int(idx) + 2, "issues": row_issues})

    return {
        "total_records": len(df),
        "valid_records": valid_count,
        "warning_records": warning_count,
        "error_records": error_count,
        "issues": issues[:100],
    }


def build_mapping_dict(mappings: list[dict[str, str]]) -> dict[str, str]:
    return {m["target_field"]: m["source_column"] for m in mappings}


async def import_valid_records(
    db: AsyncSession,
    business_id: int,
    dataset_type: str,
    file_path: str,
    filename: str,
    mappings: list[dict[str, str]],
) -> dict[str, Any]:
    from app.models import (
        Category,
        Customer,
        Inventory,
        MarketingSpend,
        Order,
        Product,
        Return,
        WebsiteEvent,
    )

    mapping_dict = build_mapping_dict(mappings)
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)

    imported = 0
    skipped = 0
    failed = 0
    reasons: dict[str, int] = {}
    source = f"file:{filename}"
    total_rows = len(df)

    def log_failure(reason: str):
        nonlocal failed
        failed += 1
        reasons[reason] = reasons.get(reason, 0) + 1

    for idx, row in df.iterrows():
        row_dict = {str(k): row[k] for k in df.columns}

        if dataset_type == "products":
            category_name = _get_mapped_value(row_dict, mapping_dict, "category")
            category_id = None
            if category_name:
                from sqlalchemy import select

                result = await db.execute(
                    select(Category).where(Category.business_id == business_id, Category.name == str(category_name))
                )
                category = result.scalar_one_or_none()
                if not category:
                    category = Category(business_id=business_id, name=str(category_name), source=source)
                    db.add(category)
                    await db.flush()
                category_id = category.id

            prod_name = str(_get_mapped_value(row_dict, mapping_dict, "name", "")).strip()
            if not prod_name:
                log_failure("Missing product name")
                continue

            product = Product(
                business_id=business_id,
                category_id=category_id,
                sku=str(_get_mapped_value(row_dict, mapping_dict, "sku", "")) or None,
                name=prod_name,
                price=_parse_float(_get_mapped_value(row_dict, mapping_dict, "price")),
                cost_price=_parse_float(_get_mapped_value(row_dict, mapping_dict, "cost_price"), default=None),
                stock=_parse_int(_get_mapped_value(row_dict, mapping_dict, "stock")),
                source=source,
                source_record_id=str(_get_mapped_value(row_dict, mapping_dict, "sku", imported)),
            )
            db.add(product)
            imported += 1

        elif dataset_type == "customers":
            cust_email = str(_get_mapped_value(row_dict, mapping_dict, "email", "")).strip()
            cust_name = str(_get_mapped_value(row_dict, mapping_dict, "name", "")).strip()
            if not cust_email and not cust_name:
                log_failure("Missing customer email and name")
                continue
            customer = Customer(
                business_id=business_id,
                name=cust_name or None,
                email=cust_email or None,
                region=str(_get_mapped_value(row_dict, mapping_dict, "region", "")) or None,
                city=str(_get_mapped_value(row_dict, mapping_dict, "city", "")) or None,
                country=str(_get_mapped_value(row_dict, mapping_dict, "country", "")) or None,
                source=source,
                source_record_id=cust_email or str(imported),
            )
            db.add(customer)
            imported += 1

        elif dataset_type == "orders":
            order_date = _parse_date(_get_mapped_value(row_dict, mapping_dict, "order_date"))
            if not order_date:
                log_failure("Invalid or missing order_date")
                continue
            order = Order(
                business_id=business_id,
                order_date=order_date,
                status=str(_get_mapped_value(row_dict, mapping_dict, "status", "delivered")),
                subtotal=_parse_float(_get_mapped_value(row_dict, mapping_dict, "subtotal")),
                discount=_parse_float(_get_mapped_value(row_dict, mapping_dict, "discount")),
                shipping_cost=_parse_float(_get_mapped_value(row_dict, mapping_dict, "shipping_cost")),
                tax=_parse_float(_get_mapped_value(row_dict, mapping_dict, "tax")),
                payment_fee=_parse_float(_get_mapped_value(row_dict, mapping_dict, "payment_fee")),
                total_amount=_parse_float(_get_mapped_value(row_dict, mapping_dict, "total_amount")),
                payment_method=str(_get_mapped_value(row_dict, mapping_dict, "payment_method", "")) or None,
                sales_channel=str(_get_mapped_value(row_dict, mapping_dict, "sales_channel", "")) or None,
                source=source,
                source_record_id=str(_get_mapped_value(row_dict, mapping_dict, "order_id", imported)),
            )
            db.add(order)
            imported += 1

        elif dataset_type == "inventory":
            inv = Inventory(
                business_id=business_id,
                product_id=1,
                stock_quantity=_parse_int(_get_mapped_value(row_dict, mapping_dict, "stock_quantity")),
                reorder_level=_parse_int(_get_mapped_value(row_dict, mapping_dict, "reorder_level", 10)),
                source=source,
                source_record_id=str(_get_mapped_value(row_dict, mapping_dict, "product_id", imported)),
            )
            db.add(inv)
            imported += 1

        elif dataset_type == "returns":
            return_date = _parse_date(_get_mapped_value(row_dict, mapping_dict, "return_date"))
            if not return_date:
                log_failure("Invalid or missing return_date")
                continue
            ret = Return(
                business_id=business_id,
                quantity=_parse_int(_get_mapped_value(row_dict, mapping_dict, "quantity", 1)),
                reason=str(_get_mapped_value(row_dict, mapping_dict, "reason", "")) or None,
                refund_amount=_parse_float(_get_mapped_value(row_dict, mapping_dict, "refund_amount")),
                return_date=return_date,
                source=source,
                source_record_id=str(_get_mapped_value(row_dict, mapping_dict, "order_id", imported)),
            )
            db.add(ret)
            imported += 1

        elif dataset_type == "marketing":
            spend_date = _parse_date(_get_mapped_value(row_dict, mapping_dict, "date"))
            if not spend_date:
                log_failure("Invalid or missing spend date")
                continue
            ms = MarketingSpend(
                business_id=business_id,
                campaign=str(_get_mapped_value(row_dict, mapping_dict, "campaign", "")) or None,
                channel=str(_get_mapped_value(row_dict, mapping_dict, "channel", "")) or None,
                spend=_parse_float(_get_mapped_value(row_dict, mapping_dict, "spend")),
                date=spend_date,
                revenue=_parse_float(_get_mapped_value(row_dict, mapping_dict, "revenue"), default=None),
                conversions=_parse_int(_get_mapped_value(row_dict, mapping_dict, "conversions"), default=None),
                source=source,
                source_record_id=str(imported),
            )
            db.add(ms)
            imported += 1

        elif dataset_type == "events":
            event_date = _parse_date(_get_mapped_value(row_dict, mapping_dict, "event_date"))
            if not event_date:
                log_failure("Invalid or missing event_date")
                continue
            event = WebsiteEvent(
                business_id=business_id,
                session_id=str(_get_mapped_value(row_dict, mapping_dict, "session_id", "")) or None,
                visitor_id=str(_get_mapped_value(row_dict, mapping_dict, "visitor_id", "")) or None,
                event_type=str(_get_mapped_value(row_dict, mapping_dict, "event_type", "unknown")),
                event_date=event_date,
                source=source,
                source_record_id=str(imported),
            )
            db.add(event)
            imported += 1

    await db.flush()
    from app.analytics.engine import invalidate_analytics_cache
    invalidate_analytics_cache(business_id)

    return {
        "total_rows": total_rows,
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "reasons": reasons,
    }
