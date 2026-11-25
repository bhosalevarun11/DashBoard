import json
import re
from typing import Any

import pandas as pd

DATASET_SIGNATURES: dict[str, list[str]] = {
    "orders": ["order_id", "order_date", "total_amount", "customer_id", "status"],
    "products": ["sku", "name", "price", "product_id", "cost_price"],
    "customers": ["customer_id", "email", "name", "country", "region"],
    "inventory": ["stock_quantity", "reorder_level", "product_id", "stock"],
    "returns": ["return_date", "refund_amount", "reason", "return_id"],
    "marketing": ["campaign", "channel", "spend", "conversions"],
    "events": ["event_type", "session_id", "visitor_id", "event_date"],
}

FILENAME_HINTS: dict[str, list[str]] = {
    "orders": ["order", "sales"],
    "products": ["product", "catalog"],
    "customers": ["customer", "client"],
    "inventory": ["inventory", "stock"],
    "returns": ["return", "refund"],
    "marketing": ["marketing", "campaign", "ads"],
    "events": ["event", "analytics", "session"],
}

COLUMN_ALIASES: dict[str, dict[str, list[str]]] = {
    "orders": {
        "order_id": ["order_id", "order_number", "order_no", "id"],
        "customer_id": ["customer_id", "customer_email", "buyer_id"],
        "order_date": ["order_date", "date", "created_at", "purchase_date"],
        "status": ["status", "order_status"],
        "subtotal": ["subtotal", "sub_total"],
        "discount": ["discount", "discount_amount"],
        "shipping_cost": ["shipping_cost", "shipping", "shipping_fee"],
        "tax": ["tax", "tax_amount", "gst"],
        "total_amount": ["total_amount", "total", "amount", "grand_total"],
        "payment_method": ["payment_method", "payment_type"],
        "sales_channel": ["sales_channel", "channel", "source"],
    },
    "products": {
        "sku": ["sku", "product_sku", "item_code"],
        "name": ["name", "product_name", "title"],
        "price": ["price", "unit_price", "selling_price"],
        "cost_price": ["cost_price", "cost", "unit_cost"],
        "stock": ["stock", "stock_quantity", "quantity"],
        "category": ["category", "category_name"],
    },
    "customers": {
        "name": ["name", "customer_name", "full_name"],
        "email": ["email", "customer_email"],
        "region": ["region", "state", "province"],
        "city": ["city", "town"],
        "country": ["country", "nation"],
    },
    "inventory": {
        "product_id": ["product_id", "sku", "product_sku"],
        "stock_quantity": ["stock_quantity", "stock", "quantity_on_hand"],
        "reorder_level": ["reorder_level", "min_stock", "reorder_point"],
    },
    "returns": {
        "order_id": ["order_id", "order_number"],
        "product_id": ["product_id", "sku"],
        "quantity": ["quantity", "qty", "return_qty"],
        "reason": ["reason", "return_reason"],
        "refund_amount": ["refund_amount", "refund", "amount"],
        "return_date": ["return_date", "date", "created_at"],
    },
    "marketing": {
        "campaign": ["campaign", "campaign_name"],
        "channel": ["channel", "source", "platform"],
        "spend": ["spend", "cost", "ad_spend"],
        "date": ["date", "spend_date"],
        "revenue": ["revenue", "attributed_revenue"],
        "conversions": ["conversions", "orders", "purchases"],
    },
}


def normalize_column(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", name.strip().lower()).strip("_")


def detect_dataset(filename: str, columns: list[str]) -> tuple[str | None, float]:
    normalized = [normalize_column(c) for c in columns]
    filename_lower = filename.lower()
    scores: dict[str, float] = {}

    for dataset, signatures in DATASET_SIGNATURES.items():
        score = 0.0
        for sig in signatures:
            if normalize_column(sig) in normalized:
                score += 2.0
        for hint in FILENAME_HINTS.get(dataset, []):
            if hint in filename_lower:
                score += 1.0
        scores[dataset] = score

    if not scores or max(scores.values()) < 2:
        return None, 0.0
    best = max(scores, key=scores.get)
    return best, scores[best]


def suggest_column_mappings(dataset_type: str, columns: list[str]) -> list[dict[str, str]]:
    aliases = COLUMN_ALIASES.get(dataset_type, {})
    normalized_cols = {normalize_column(c): c for c in columns}
    mappings: list[dict[str, str]] = []
    used_targets: set[str] = set()

    for target, options in aliases.items():
        for option in options:
            norm = normalize_column(option)
            if norm in normalized_cols and target not in used_targets:
                mappings.append({"source_column": normalized_cols[norm], "target_field": target})
                used_targets.add(target)
                break
    return mappings


def inspect_file(file_path: str, filename: str) -> dict[str, Any]:
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_path, nrows=500)
    else:
        df = pd.read_csv(file_path, nrows=500)

    columns = [str(c) for c in df.columns.tolist()]
    dataset_type, confidence = detect_dataset(filename, columns)
    sample_rows = json.loads(df.head(5).fillna("").to_json(orient="records", date_format="iso"))
    dtypes = {str(k): str(v) for k, v in df.dtypes.items()}

    return {
        "filename": filename,
        "columns": columns,
        "dtypes": dtypes,
        "row_count_sample": len(df),
        "sample_rows": sample_rows,
        "detected_dataset": dataset_type,
        "confidence": confidence,
        "suggested_mappings": suggest_column_mappings(dataset_type, columns) if dataset_type else [],
    }
