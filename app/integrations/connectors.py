import base64
import hashlib
import hmac
import json
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value, encrypt_value
from app.models import DataSource, DataSourceStatus, DataSourceType


def verify_shopify_hmac(raw_body: bytes, hmac_header: str, secret: str) -> bool:
    """Timing-safe verification of Shopify webhook HMAC signatures (OWASP Phase 7)."""
    if not hmac_header or not secret:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    computed_hmac = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(computed_hmac, hmac_header)


async def test_database_connection(
    db_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    ssl: bool = False,
) -> dict[str, Any]:
    if db_type == "postgresql":
        url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database_name}"
        if ssl:
            url += "?ssl=require"
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(url, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"success": True, "message": "Connection successful"}
        except Exception as exc:
            msg = str(exc)
            if password:
                msg = msg.replace(password, "******")
            return {"success": False, "message": f"Connection failed: {msg}"}
        finally:
            await engine.dispose()

    if db_type == "mysql":
        url = f"mysql+aiomysql://{username}:{password}@{host}:{port}/{database_name}"
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(url, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"success": True, "message": "Connection successful"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        finally:
            await engine.dispose()

    return {"success": False, "message": f"Database type '{db_type}' test not configured in this environment."}


async def create_database_source(
    db: AsyncSession,
    business_id: int,
    name: str,
    db_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    ssl: bool,
) -> DataSource:
    config = {
        "db_type": db_type,
        "host": host,
        "port": port,
        "database_name": database_name,
        "username": username,
        "password": password,
        "ssl": ssl,
    }
    source = DataSource(
        business_id=business_id,
        name=name,
        source_type=DataSourceType(db_type),
        status=DataSourceStatus.connected,
        config_encrypted=encrypt_value(json.dumps(config)),
    )
    db.add(source)
    await db.flush()
    return source


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    masked = dict(config)
    if "password" in masked:
        masked["password"] = "********"
    if "consumer_secret" in masked:
        masked["consumer_secret"] = "********"
    if "access_token" in masked:
        masked["access_token"] = "********"
    return masked


async def sync_shopify(db: AsyncSession, source: DataSource) -> int:
    if not source.config_encrypted:
        return 0
    config = json.loads(decrypt_value(source.config_encrypted))
    shop = config["shop_domain"].replace("https://", "").replace("http://", "").rstrip("/")
    token = config["access_token"]
    headers = {"X-Shopify-Access-Token": token}
    imported = 0
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"https://{shop}/admin/api/2024-10/products.json?limit=50", headers=headers)
        if resp.status_code == 200:
            imported += len(resp.json().get("products", []))
    source.records_imported += imported
    source.status = DataSourceStatus.connected
    source.last_error = None
    return imported


async def sync_woocommerce(db: AsyncSession, source: DataSource) -> int:
    if not source.config_encrypted:
        return 0
    config = json.loads(decrypt_value(source.config_encrypted))
    store_url = config["store_url"].rstrip("/")
    auth = (config["consumer_key"], config["consumer_secret"])
    imported = 0
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{store_url}/wp-json/wc/v3/products?per_page=50", auth=auth)
        if resp.status_code == 200:
            imported += len(resp.json())
    source.records_imported += imported
    source.status = DataSourceStatus.connected
    source.last_error = None
    return imported


def parse_dt(val: Any) -> datetime:
    from dateutil.parser import parse as parse_date
    if isinstance(val, datetime):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return parse_date(val)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def parse_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def find_key(row_dict: dict[str, Any], candidates: list[str]) -> Any:
    lower_keys = {k.lower().replace("-", "_").replace(" ", "_"): k for k in row_dict.keys()}
    for cand in candidates:
        c_norm = cand.lower().replace("-", "_").replace(" ", "_")
        if c_norm in lower_keys:
            return row_dict[lower_keys[c_norm]]
    return None


async def sync_database_source(db: AsyncSession, source: DataSource) -> int:
    if not source.config_encrypted:
        return 0
    config = json.loads(decrypt_value(source.config_encrypted))
    db_type = config.get("db_type", "postgresql")
    host = config.get("host", "localhost")
    port = config.get("port", 5432)
    database_name = config.get("database_name", "dashboard")
    username = config.get("username", "")
    password = config.get("password", "")
    ssl = config.get("ssl", False)

    imported = 0
    if db_type == "postgresql":
        url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database_name}"
        if ssl:
            url += "?ssl=require"
    elif db_type == "mysql":
        url = f"mysql+aiomysql://{username}:{password}@{host}:{port}/{database_name}"
    else:
        return 0

    from datetime import datetime, timezone
    import uuid
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.models import Customer, Inventory, MarketingSpend, Order, OrderItem, Product, Return

    try:
        remote_engine = create_async_engine(url, pool_pre_ping=True)
        async with remote_engine.connect() as conn:
            # 1. Inspect table names in remote database
            try:
                tables_result = await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema IN ('public', 'main', 'dbo') AND table_type = 'BASE TABLE'"
                    )
                )
                tables = [r[0] for r in tables_result.all()]
            except Exception:
                tables = []

            if not tables:
                tables = ["orders", "products", "customers", "returns", "marketing_spend", "inventory", "order_items"]

            for table_name in tables:
                t_lower = table_name.lower()
                try:
                    res = await conn.execute(text(f'SELECT * FROM "{table_name}" LIMIT 2000'))
                    rows = [dict(r) for r in res.mappings().all()]
                    if not rows:
                        continue

                    cols_lower = [k.lower() for k in rows[0].keys()]

                    # A. Orders Table Sync
                    is_orders = any(k in t_lower for k in ["order", "sale", "invoice", "transaction", "checkout"]) or (
                        any(c in cols_lower for c in ["order_id", "total_amount", "subtotal", "order_date"])
                    )
                    if is_orders and "item" not in t_lower and "return" not in t_lower:
                        for r in rows:
                            s_id = str(find_key(r, ["order_id", "id", "order_number", "order_no", "source_record_id", "code"]) or uuid.uuid4().hex)
                            existing = await db.execute(
                                select(Order).where(Order.business_id == source.business_id, Order.source_record_id == s_id)
                            )
                            if not existing.scalar_one_or_none():
                                dt_val = find_key(r, ["order_date", "created_at", "date", "purchase_date", "timestamp", "time"])
                                tot_val = find_key(r, ["total_amount", "total", "amount", "grand_total", "price", "order_total"])
                                sub_val = find_key(r, ["subtotal", "sub_total", "net_amount"])
                                disc_val = find_key(r, ["discount", "discount_amount", "savings"])
                                ship_val = find_key(r, ["shipping_cost", "shipping", "shipping_fee", "freight"])
                                tax_val = find_key(r, ["tax", "tax_amount", "vat", "gst"])
                                fee_val = find_key(r, ["payment_fee", "fee", "gateway_fee"])
                                status_val = find_key(r, ["status", "order_status", "state"]) or "delivered"
                                channel_val = find_key(r, ["sales_channel", "channel", "source", "platform", "store"]) or "Direct"
                                pm_val = find_key(r, ["payment_method", "payment_type"])

                                o = Order(
                                    business_id=source.business_id,
                                    source_record_id=s_id,
                                    order_date=parse_dt(dt_val),
                                    status=str(status_val),
                                    subtotal=parse_float(sub_val, parse_float(tot_val)),
                                    discount=parse_float(disc_val),
                                    shipping_cost=parse_float(ship_val),
                                    tax=parse_float(tax_val),
                                    payment_fee=parse_float(fee_val),
                                    total_amount=parse_float(tot_val),
                                    payment_method=str(pm_val) if pm_val else None,
                                    sales_channel=str(channel_val),
                                    source=source.source_type.value,
                                )
                                db.add(o)
                                imported += 1

                    # B. Products Table Sync
                    is_products = any(k in t_lower for k in ["product", "catalog", "item", "sku"]) or (
                        any(c in cols_lower for c in ["sku", "cost_price", "price", "product_name"])
                    )
                    if is_products and "order" not in t_lower:
                        for r in rows:
                            sku_val = str(find_key(r, ["sku", "product_sku", "item_code", "product_id", "id"]) or "")
                            name_val = str(find_key(r, ["name", "product_name", "title", "item_name"]) or "Unnamed Product")
                            price_val = parse_float(find_key(r, ["price", "unit_price", "selling_price", "mrp"]))
                            cost_val = parse_float(find_key(r, ["cost_price", "cost", "unit_cost", "cogs"]))
                            stock_val = parse_int(find_key(r, ["stock", "stock_quantity", "quantity", "qty"]))
                            s_id = str(find_key(r, ["source_record_id", "id", "product_id"]) or sku_val)

                            if sku_val:
                                existing = await db.execute(
                                    select(Product).where(Product.business_id == source.business_id, Product.sku == sku_val)
                                )
                                if not existing.scalar_one_or_none():
                                    p = Product(
                                        business_id=source.business_id,
                                        sku=sku_val,
                                        name=name_val,
                                        price=price_val,
                                        cost_price=cost_val if cost_val > 0 else None,
                                        stock=stock_val,
                                        source=source.source_type.value,
                                        source_record_id=s_id,
                                    )
                                    db.add(p)
                                    imported += 1

                    # C. Customers Table Sync
                    is_customers = any(k in t_lower for k in ["customer", "user", "client", "buyer"]) or (
                        any(c in cols_lower for c in ["customer_email", "email", "customer_id"])
                    )
                    if is_customers and "order" not in t_lower:
                        for r in rows:
                            email_val = str(find_key(r, ["email", "customer_email", "email_address"]) or "")
                            name_val = str(find_key(r, ["name", "customer_name", "full_name"]) or "")
                            reg_val = str(find_key(r, ["region", "state", "province"]) or "")
                            city_val = str(find_key(r, ["city", "town"]) or "")
                            country_val = str(find_key(r, ["country", "nation"]) or "")
                            s_id = str(find_key(r, ["customer_id", "id", "user_id"]) or email_val)

                            if email_val or name_val:
                                existing = await db.execute(
                                    select(Customer).where(Customer.business_id == source.business_id, Customer.email == email_val if email_val else Customer.name == name_val)
                                )
                                if not existing.scalar_one_or_none():
                                    c = Customer(
                                        business_id=source.business_id,
                                        name=name_val or None,
                                        email=email_val or None,
                                        region=reg_val or None,
                                        city=city_val or None,
                                        country=country_val or None,
                                        source=source.source_type.value,
                                        source_record_id=s_id,
                                    )
                                    db.add(c)
                                    imported += 1

                    # D. Returns Table Sync
                    is_returns = any(k in t_lower for k in ["return", "refund"])
                    if is_returns:
                        for r in rows:
                            refund_val = parse_float(find_key(r, ["refund_amount", "refund", "amount"]))
                            dt_val = find_key(r, ["return_date", "date", "refund_date", "created_at"])
                            reason_val = str(find_key(r, ["reason", "return_reason", "notes"]) or "Return")
                            s_id = str(find_key(r, ["return_id", "id", "refund_id"]) or uuid.uuid4().hex)

                            existing = await db.execute(
                                select(Return).where(Return.business_id == source.business_id, Return.source_record_id == s_id)
                            )
                            if not existing.scalar_one_or_none():
                                ret = Return(
                                    business_id=source.business_id,
                                    refund_amount=refund_val,
                                    return_date=parse_dt(dt_val),
                                    reason=reason_val,
                                    source=source.source_type.value,
                                    source_record_id=s_id,
                                )
                                db.add(ret)
                                imported += 1

                    # E. Marketing Spend Table Sync
                    is_marketing = any(k in t_lower for k in ["marketing", "ad_spend", "campaign", "ad"]) or (
                        any(c in cols_lower for c in ["ad_spend", "spend", "conversions"])
                    )
                    if is_marketing:
                        for r in rows:
                            chan_val = str(find_key(r, ["channel", "source", "platform"]) or "Other")
                            spend_val = parse_float(find_key(r, ["spend", "cost", "ad_spend", "amount"]))
                            rev_val = parse_float(find_key(r, ["revenue", "attributed_revenue"]))
                            conv_val = parse_int(find_key(r, ["conversions", "orders", "purchases"]))
                            dt_val = find_key(r, ["date", "spend_date", "created_at"])
                            camp_val = str(find_key(r, ["campaign", "campaign_name"]) or "Campaign")
                            s_id = str(find_key(r, ["id", "campaign_id"]) or uuid.uuid4().hex)

                            existing = await db.execute(
                                select(MarketingSpend).where(MarketingSpend.business_id == source.business_id, MarketingSpend.source_record_id == s_id)
                            )
                            if not existing.scalar_one_or_none():
                                m_spend = MarketingSpend(
                                    business_id=source.business_id,
                                    channel=chan_val,
                                    spend=spend_val,
                                    revenue=rev_val if rev_val > 0 else None,
                                    conversions=conv_val if conv_val > 0 else None,
                                    date=parse_dt(dt_val),
                                    campaign=camp_val,
                                    source=source.source_type.value,
                                    source_record_id=s_id,
                                )
                                db.add(m_spend)
                                imported += 1

                except Exception:
                    pass

        await remote_engine.dispose()
    except Exception as exc:
        source.last_error = str(exc)
        source.status = DataSourceStatus.error
        return 0

    from datetime import datetime, timezone
    from app.analytics.engine import invalidate_analytics_cache
    invalidate_analytics_cache(source.business_id)

    source.records_imported += imported
    source.status = DataSourceStatus.connected
    source.last_error = None
    source.last_sync_at = datetime.now(timezone.utc)
    return imported
