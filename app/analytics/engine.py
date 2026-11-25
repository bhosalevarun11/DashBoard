import math
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Category,
    Customer,
    DashboardLayout,
    Inventory,
    MarketingSpend,
    Order,
    OrderItem,
    Product,
    Return,
    WebsiteEvent,
)
from app.schemas import AnalyticsResponse, ChartSeries, DataAvailability, DateRangeFilter, KPICard

_AVAILABILITY_CACHE: dict[int, tuple[float, DataAvailability]] = {}
_ANALYTICS_CACHE: dict[str, tuple[float, AnalyticsResponse]] = {}


def invalidate_analytics_cache(business_id: int | None = None) -> None:
    global _AVAILABILITY_CACHE, _ANALYTICS_CACHE
    if business_id is None:
        _AVAILABILITY_CACHE.clear()
        _ANALYTICS_CACHE.clear()
    else:
        _AVAILABILITY_CACHE.pop(business_id, None)
        keys_to_del = [k for k in _ANALYTICS_CACHE if k.startswith(f"{business_id}:")]
        for k in keys_to_del:
            _ANALYTICS_CACHE.pop(k, None)


def _default_date_range(filters: DateRangeFilter) -> tuple[datetime, datetime]:
    end = filters.end_date or datetime.now(timezone.utc)
    start = filters.start_date or (end - timedelta(days=365 * 10))
    return start, end


def _previous_period(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    delta = end - start
    return start - delta, start


def _pct_change(cur: float, prev: float) -> float | None:
    if prev == 0:
        return None
    return round(((cur - prev) / prev) * 100, 1)


async def get_data_availability(db: AsyncSession, business_id: int) -> DataAvailability:
    now = time.time()
    if business_id in _AVAILABILITY_CACHE:
        ts, cached_val = _AVAILABILITY_CACHE[business_id]
        if now - ts < 60.0:  # 60 second TTL
            return cached_val

    async def has_records(model) -> bool:
        result = await db.execute(
            select(func.count(model.id)).where(model.business_id == business_id)
        )
        return (result.scalar() or 0) > 0

    val = DataAvailability(
        orders=await has_records(Order),
        products=await has_records(Product),
        customers=await has_records(Customer),
        inventory=await has_records(Inventory),
        returns=await has_records(Return),
        marketing=await has_records(MarketingSpend),
        events=await has_records(WebsiteEvent),
    )
    _AVAILABILITY_CACHE[business_id] = (now, val)
    return val


def _order_filters(business_id: int, start: datetime, end: datetime, filters: DateRangeFilter):
    conditions = [
        Order.business_id == business_id,
        Order.order_date >= start,
        Order.order_date <= end,
    ]
    if filters.order_status:
        conditions.append(Order.status == filters.order_status)
    if filters.sales_channel:
        conditions.append(Order.sales_channel == filters.sales_channel)
    if filters.payment_method:
        conditions.append(Order.payment_method == filters.payment_method)
    if filters.customer_id:
        conditions.append(Order.customer_id == filters.customer_id)
    return and_(*conditions)


async def _sum_orders(db: AsyncSession, business_id: int, start: datetime, end: datetime, filters: DateRangeFilter) -> dict[str, float]:
    cond = _order_filters(business_id, start, end, filters)
    result = await db.execute(
        select(
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(Order.subtotal), 0),
            func.coalesce(func.sum(Order.discount), 0),
            func.coalesce(func.sum(Order.shipping_cost), 0),
            func.coalesce(func.sum(Order.tax), 0),
            func.count(Order.id),
        ).where(cond)
    )
    total, subtotal, discount, shipping, tax, count = result.one()
    return {
        "revenue": float(total),
        "subtotal": float(subtotal),
        "discounts": float(discount),
        "shipping": float(shipping),
        "tax": float(tax),
        "orders": int(count),
    }


async def _profit_estimate(db: AsyncSession, business_id: int, start: datetime, end: datetime) -> tuple[float, bool]:
    result = await db.execute(
        select(
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_cost), 0),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.business_id == business_id,
            Order.order_date >= start,
            Order.order_date <= end,
        )
    )
    revenue, cost = result.one()
    has_cost = cost is not None and float(cost) > 0
    if has_cost:
        return float(revenue) - float(cost), True
    return 0.0, False


async def get_executive_dashboard(
    db: AsyncSession,
    business_id: int,
    filters: DateRangeFilter,
) -> AnalyticsResponse:
    start, end = _default_date_range(filters)
    prev_start, prev_end = _previous_period(start, end)
    
    cache_key = f"{business_id}:dashboard:{start.isoformat()}:{end.isoformat()}:{filters.granularity}:{filters.order_status}:{filters.sales_channel}"
    now_ts = time.time()
    if cache_key in _ANALYTICS_CACHE:
        ts, cached_res = _ANALYTICS_CACHE[cache_key]
        if now_ts - ts < 30.0:  # 30 second TTL
            return cached_res

    availability = await get_data_availability(db, business_id)

    if not availability.orders:
        kpis = [
            KPICard(key="revenue", label="Total Revenue", value=0, unavailable_reason="Upload order data to activate Executive Dashboard."),
            KPICard(key="orders", label="Total Orders", value=0, unavailable_reason="Order data not uploaded."),
        ]
        return AnalyticsResponse(kpis=kpis, charts=[], meta={"availability": availability.model_dump()})

    current = await _sum_orders(db, business_id, start, end, filters)
    previous = await _sum_orders(db, business_id, prev_start, prev_end, filters)
    profit, has_cost = await _profit_estimate(db, business_id, start, end)
    prev_profit, _ = await _profit_estimate(db, business_id, prev_start, prev_end)

    net_revenue = current["revenue"] - current["discounts"]
    prev_net = previous["revenue"] - previous["discounts"]

    customer_count = 0
    if availability.customers:
        result = await db.execute(select(func.count(Customer.id)).where(Customer.business_id == business_id))
        customer_count = result.scalar() or 0

    has_items_res = await db.execute(
        select(func.count(OrderItem.id)).join(Order, Order.id == OrderItem.order_id).where(Order.business_id == business_id)
    )
    has_item_records = (has_items_res.scalar() or 0) > 0

    units_sold = None
    if has_item_records:
        result = await db.execute(
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.business_id == business_id, Order.order_date >= start, Order.order_date <= end)
        )
        units_sold = int(result.scalar() or 0)

    return_rate = None
    if availability.returns and current["orders"] > 0:
        ret_count = await db.execute(
            select(func.count(Return.id)).where(
                Return.business_id == business_id,
                Return.return_date >= start,
                Return.return_date <= end,
            )
        )
        return_rate = round((ret_count.scalar() or 0) / current["orders"] * 100, 1)

    has_orders = current["orders"] > 0
    aov = round(current["revenue"] / current["orders"], 2) if has_orders else None
    prev_aov = round(previous["revenue"] / previous["orders"], 2) if previous["orders"] > 0 else None
    margin = round((profit / current["revenue"]) * 100, 1) if (has_cost and current["revenue"] > 0) else None

    returning_rate = None
    if availability.customers and current["orders"] > 0:
        subq = (
            select(Order.customer_id)
            .where(Order.business_id == business_id, Order.customer_id.isnot(None))
            .group_by(Order.customer_id)
            .having(func.count(Order.id) > 1)
            .subquery()
        )
        ret_res = await db.execute(select(func.count()).select_from(subq))
        tot_cust_res = await db.execute(
            select(func.count(func.distinct(Order.customer_id))).where(Order.business_id == business_id, Order.customer_id.isnot(None))
        )
        tot_cust = tot_cust_res.scalar() or 0
        ret_cust = ret_res.scalar() or 0
        if tot_cust > 0:
            returning_rate = round((ret_cust / tot_cust) * 100, 1)

    kpis = [
        KPICard(key="revenue", label="Total Revenue", value=round(current["revenue"], 2), change_pct=_pct_change(current["revenue"], previous["revenue"]), format="currency"),
        KPICard(key="net_revenue", label="Net Revenue", value=round(net_revenue, 2), change_pct=_pct_change(net_revenue, prev_net), format="currency"),
        KPICard(
            key="profit",
            label="Total Profit",
            value=round(profit, 2) if has_cost else None,
            change_pct=_pct_change(profit, prev_profit) if has_cost else None,
            format="currency",
            unavailable_reason=None if has_cost else "Product cost data required — cost price not configured.",
        ),
        KPICard(
            key="margin",
            label="Profit Margin",
            value=margin if margin is not None else None,
            format="percent",
            unavailable_reason=None if (has_cost and current["revenue"] > 0) else "Requires product cost data.",
        ),
        KPICard(key="orders", label="Total Orders", value=current["orders"], change_pct=_pct_change(current["orders"], previous["orders"])),
        KPICard(
            key="customers",
            label="Total Customers",
            value=customer_count if availability.customers else None,
            unavailable_reason=None if availability.customers else "Customer data not uploaded.",
        ),
        KPICard(
            key="aov",
            label="Average Order Value",
            value=aov,
            change_pct=_pct_change(aov, prev_aov) if (aov is not None and prev_aov is not None) else None,
            format="currency",
            unavailable_reason=None if has_orders else "No orders in selected range.",
        ),
        KPICard(
            key="returning_rate",
            label="Returning Customer Rate",
            value=returning_rate,
            format="percent",
            unavailable_reason=None if availability.customers else "Customer data not uploaded.",
        ),
        KPICard(
            key="units",
            label="Products Sold",
            value=units_sold,
            unavailable_reason=None if has_item_records else "Quantity data unavailable — order item details not uploaded.",
        ),
        KPICard(
            key="return_rate",
            label="Return Rate",
            value=return_rate,
            format="percent",
            unavailable_reason=None if availability.returns else "Return data not uploaded.",
        ),
    ]

    charts = await _revenue_over_time(db, business_id, start, end, filters)
    res_response = AnalyticsResponse(kpis=kpis, charts=charts, meta={"availability": availability.model_dump()})
    _ANALYTICS_CACHE[cache_key] = (now_ts, res_response)
    return res_response


async def _revenue_over_time(
    db: AsyncSession,
    business_id: int,
    start: datetime,
    end: datetime,
    filters: DateRangeFilter,
) -> list[ChartSeries]:
    is_sqlite = db.bind and db.bind.dialect.name == "sqlite"
    if is_sqlite:
        if filters.granularity == "weekly":
            bucket = func.strftime("%Y-%W", Order.order_date).label("period")
        elif filters.granularity == "monthly":
            bucket = func.strftime("%Y-%m", Order.order_date).label("period")
        else:
            bucket = func.strftime("%Y-%m-%d", Order.order_date).label("period")
    else:
        trunc = "day"
        if filters.granularity == "weekly":
            trunc = "week"
        elif filters.granularity == "monthly":
            trunc = "month"
        bucket = func.date_trunc(trunc, Order.order_date).label("period")

    result = await db.execute(
        select(bucket, func.coalesce(func.sum(Order.total_amount), 0), func.count(Order.id))
        .where(_order_filters(business_id, start, end, filters))
        .group_by(bucket)
        .order_by(bucket)
    )
    data = []
    for row in result.all():
        period_str = str(row[0]) if row[0] else ""
        if isinstance(row[0], (datetime, date)):

            period_str = row[0].strftime("%Y-%m-%d")
        data.append({"period": period_str, "revenue": round(float(row[1]), 2), "orders": int(row[2])})

    return [
        ChartSeries(name="revenue_over_time", data=data),
        ChartSeries(name="orders_over_time", data=[{"period": d["period"], "orders": d["orders"]} for d in data]),
    ]


async def get_sales_analytics(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    start, end = _default_date_range(filters)
    prev_start, prev_end = _previous_period(start, end)
    availability = await get_data_availability(db, business_id)

    if not availability.orders:
        return AnalyticsResponse(
            kpis=[KPICard(key="sales", label="Sales", value=0, unavailable_reason="Upload order data to activate Sales Analytics.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    cur = await _sum_orders(db, business_id, start, end, filters)
    prev = await _sum_orders(db, business_id, prev_start, prev_end, filters)
    profit, has_cost = await _profit_estimate(db, business_id, start, end)
    gross_sales = cur["subtotal"]
    net_sales = cur["revenue"] - cur["discounts"]

    # Channel breakdown
    chan_res = await db.execute(
        select(
            func.coalesce(Order.sales_channel, "Direct").label("channel"),
            func.sum(Order.total_amount),
            func.count(Order.id),
        )
        .where(_order_filters(business_id, start, end, filters))
        .group_by(Order.sales_channel)
    )
    sales_by_channel = [{"channel": row[0], "revenue": round(float(row[1] or 0), 2), "orders": int(row[2])} for row in chan_res.all()]

    # Sales by region
    reg_res = await db.execute(
        select(
            func.coalesce(Customer.region, "Unknown").label("region"),
            func.sum(Order.total_amount),
            func.count(Order.id),
        )
        .join(Customer, Customer.id == Order.customer_id, isouter=True)
        .where(_order_filters(business_id, start, end, filters))
        .group_by(Customer.region)
    )
    sales_by_region = [{"region": row[0], "revenue": round(float(row[1] or 0), 2), "orders": int(row[2])} for row in reg_res.all()]

    kpis = [
        KPICard(key="gross_sales", label="Gross Sales", value=round(gross_sales, 2), format="currency"),
        KPICard(key="net_sales", label="Net Sales", value=round(net_sales, 2), change_pct=_pct_change(net_sales, prev["revenue"] - prev["discounts"]), format="currency"),
        KPICard(key="revenue", label="Total Revenue", value=round(cur["revenue"], 2), change_pct=_pct_change(cur["revenue"], prev["revenue"]), format="currency"),
        KPICard(key="orders", label="Total Orders", value=cur["orders"], change_pct=_pct_change(cur["orders"], prev["orders"])),
        KPICard(key="aov", label="Average Order Value", value=round(cur["revenue"] / cur["orders"], 2) if cur["orders"] else 0, format="currency"),
        KPICard(key="discounts", label="Total Discounts", value=round(cur["discounts"], 2), format="currency"),
        KPICard(key="taxes", label="Total Taxes", value=round(cur["tax"], 2), format="currency"),
        KPICard(key="shipping", label="Shipping Fees", value=round(cur["shipping"], 2), format="currency"),
        KPICard(key="profit", label="Total Profit", value=round(profit, 2) if has_cost else "N/A", format="currency" if has_cost else "text", unavailable_reason=None if has_cost else "Requires product cost data."),
    ]

    charts = await _revenue_over_time(db, business_id, start, end, filters)
    charts.append(ChartSeries(name="sales_by_channel", data=sales_by_channel))
    charts.append(ChartSeries(name="sales_by_region", data=sales_by_region))

    return AnalyticsResponse(kpis=kpis, charts=charts, meta={"availability": availability.model_dump()})


async def get_product_analytics(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    start, end = _default_date_range(filters)
    availability = await get_data_availability(db, business_id)

    if not availability.products:
        return AnalyticsResponse(
            kpis=[KPICard(key="products", label="Products", value=0, unavailable_reason="Upload product data to view Product Analytics.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    result = await db.execute(
        select(
            Product.id,
            Product.name,
            Product.sku,
            Product.stock,
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label("revenue"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_cost), 0).label("cost"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id, isouter=True)
        .join(Order, Order.id == OrderItem.order_id, isouter=True)
        .where(
            Product.business_id == business_id,
            (Order.order_date >= start) | (Order.id.is_(None)),
            (Order.order_date <= end) | (Order.id.is_(None)),
        )
        .group_by(Product.id, Product.name, Product.sku, Product.stock)
        .order_by(desc("revenue"))
    )

    rows = []
    total_rev = 0.0
    for r in result.all():
        rev = float(r.revenue or 0)
        cost = float(r.cost or 0)
        units = int(r.units or 0)
        total_rev += rev
        profit = rev - cost if cost > 0 else None
        margin = round((profit / rev) * 100, 1) if profit is not None and rev else None

        # Sell-through rate estimate: units sold / (units sold + remaining stock)
        total_inv = units + (r.stock or 0)
        sell_through = round((units / total_inv) * 100, 1) if total_inv > 0 else 0.0

        rows.append({
            "product_id": r.id,
            "product": r.name,
            "sku": r.sku or "N/A",
            "revenue": round(rev, 2),
            "units": units,
            "stock": r.stock or 0,
            "cost": round(cost, 2) if cost else None,
            "profit": round(profit, 2) if profit is not None else None,
            "margin": margin,
            "sell_through_rate": sell_through,
        })

    # Sort best vs worst
    best_sellers = sorted(rows, key=lambda x: x["revenue"], reverse=True)[:10]
    worst_sellers = sorted(rows, key=lambda x: x["revenue"])[:10]

    kpis = [
        KPICard(key="total_products", label="Total Products", value=len(rows)),
        KPICard(key="top_product", label="Top Product", value=best_sellers[0]["product"] if best_sellers else "N/A", format="text"),
        KPICard(key="top_revenue", label="Top Product Revenue", value=best_sellers[0]["revenue"] if best_sellers else 0, format="currency"),
    ]

    return AnalyticsResponse(
        kpis=kpis,
        charts=[
            ChartSeries(name="top_selling_products", data=best_sellers),
            ChartSeries(name="worst_selling_products", data=worst_sellers),
        ],
        tables=[{"name": "products", "rows": rows}],
        meta={"availability": availability.model_dump()},
    )


async def get_category_analytics(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    start, end = _default_date_range(filters)
    availability = await get_data_availability(db, business_id)

    result = await db.execute(
        select(
            func.coalesce(Category.name, "Uncategorized").label("category"),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label("revenue"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_cost), 0).label("cost"),
            func.count(func.distinct(Order.id)).label("orders"),
        )
        .join(Product, Product.category_id == Category.id, isouter=True)
        .join(OrderItem, OrderItem.product_id == Product.id, isouter=True)
        .join(Order, Order.id == OrderItem.order_id, isouter=True)
        .where(
            (Category.business_id == business_id) | (Product.business_id == business_id),
            (Order.order_date >= start) | (Order.id.is_(None)),
            (Order.order_date <= end) | (Order.id.is_(None)),
        )
        .group_by(Category.name)
        .order_by(desc("revenue"))
    )

    rows = []
    for r in result.all():
        rev = float(r.revenue or 0)
        cost = float(r.cost or 0)
        profit = rev - cost if cost > 0 else None
        margin = round((profit / rev) * 100, 1) if profit is not None and rev > 0 else None
        rows.append({
            "category": r.category,
            "revenue": round(rev, 2),
            "units": int(r.units or 0),
            "orders": int(r.orders or 0),
            "cost": round(cost, 2) if cost else None,
            "profit": round(profit, 2) if profit is not None else None,
            "margin": margin,
        })

    return AnalyticsResponse(
        kpis=[KPICard(key="total_categories", label="Total Categories", value=len(rows))],
        charts=[ChartSeries(name="sales_by_category", data=rows)],
        tables=[{"name": "categories", "rows": rows}],
        meta={"availability": availability.model_dump()},
    )


async def get_customer_analytics(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.customers or not availability.orders:
        return AnalyticsResponse(
            kpis=[KPICard(key="customers", label="Customers", value=0, unavailable_reason="Customer Analytics unavailable because customer or order data has not been uploaded.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    start, end = _default_date_range(filters)
    total_cust = (await db.execute(select(func.count(Customer.id)).where(Customer.business_id == business_id))).scalar() or 0
    new_cust = (await db.execute(select(func.count(Customer.id)).where(Customer.business_id == business_id, Customer.created_at >= start, Customer.created_at <= end))).scalar() or 0

    order_stats = await db.execute(
        select(
            Order.customer_id,
            func.count(Order.id).label("orders"),
            func.sum(Order.total_amount).label("spent"),
        )
        .where(Order.business_id == business_id, Order.customer_id.isnot(None))
        .group_by(Order.customer_id)
    )

    rows = order_stats.all()
    counts = [r.orders for r in rows]
    total_spent = sum(float(r.spent or 0) for r in rows)
    returning = sum(1 for c in counts if c > 1)
    one_time = sum(1 for c in counts if c == 1)
    repeat_rate = round((returning / len(counts)) * 100, 1) if counts else 0.0
    avg_clv = round(total_spent / len(counts), 2) if counts else 0.0

    # Regional distribution
    geo_res = await db.execute(
        select(
            func.coalesce(Customer.country, "Unknown").label("country"),
            func.count(Customer.id),
        )
        .where(Customer.business_id == business_id)
        .group_by(Customer.country)
    )
    by_country = [{"country": r[0], "customers": int(r[1])} for r in geo_res.all()]

    kpis = [
        KPICard(key="total_customers", label="Total Customers", value=total_cust),
        KPICard(key="new_customers", label="New Customers", value=new_cust),
        KPICard(key="returning_customers", label="Returning Customers", value=returning),
        KPICard(key="one_time_customers", label="One-Time Customers", value=one_time),
        KPICard(key="repeat_rate", label="Repeat Purchase Rate", value=f"{repeat_rate}%", format="text"),
        KPICard(key="avg_clv", label="Average Customer Lifetime Value", value=avg_clv, format="currency"),
    ]

    return AnalyticsResponse(
        kpis=kpis,
        charts=[ChartSeries(name="customers_by_country", data=by_country)],
        meta={"availability": availability.model_dump()},
    )


async def get_rfm_analysis(db: AsyncSession, business_id: int) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.customers or not availability.orders:
        return AnalyticsResponse(
            kpis=[KPICard(key="rfm", label="RFM Analysis", value="N/A", unavailable_reason="RFM requires customer and order data.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(
            Order.customer_id,
            Customer.name,
            Customer.email,
            func.max(Order.order_date).label("last_order"),
            func.count(Order.id).label("frequency"),
            func.sum(Order.total_amount).label("monetary"),
        )
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.business_id == business_id, Order.customer_id.isnot(None))
        .group_by(Order.customer_id, Customer.name, Customer.email)
    )

    segments: dict[str, int] = {
        "VIP": 0, "Loyal": 0, "Potential Loyalist": 0,
        "New Customer": 0, "At Risk": 0, "Lost Customer": 0, "One-Time Customer": 0,
    }
    segment_revenue: dict[str, float] = {k: 0.0 for k in segments}
    customer_list = []

    for cid, name, email, last_order, freq, money in result.all():
        recency_days = (now - (last_order.replace(tzinfo=timezone.utc) if last_order and last_order.tzinfo is None else (last_order or now))).days
        f = int(freq or 0)
        m = float(money or 0)

        if f == 1 and recency_days <= 30:
            seg = "New Customer"
        elif f == 1:
            seg = "One-Time Customer"
        elif recency_days > 180:
            seg = "Lost Customer"
        elif recency_days > 90:
            seg = "At Risk"
        elif f >= 5 and m >= 10000:
            seg = "VIP"
        elif f >= 3:
            seg = "Loyal"
        else:
            seg = "Potential Loyalist"

        segments[seg] += 1
        segment_revenue[seg] += m
        customer_list.append({
            "customer_id": cid,
            "name": name or f"Customer #{cid}",
            "email": email or "",
            "recency_days": recency_days,
            "frequency": f,
            "monetary": round(m, 2),
            "segment": seg,
        })

    chart_data = [
        {"segment": k, "count": v, "revenue": round(segment_revenue[k], 2), "aov": round(segment_revenue[k]/v, 2) if v else 0}
        for k, v in segments.items()
    ]

    return AnalyticsResponse(
        kpis=[
            KPICard(key="total_segmented", label="Segmented Customers", value=len(customer_list)),
            KPICard(key="vip_count", label="VIP Customers", value=segments["VIP"]),
            KPICard(key="at_risk_count", label="At-Risk Customers", value=segments["At Risk"]),
        ],
        charts=[ChartSeries(name="rfm_segments", data=chart_data)],
        tables=[
            {"name": "rfm_summary", "rows": chart_data},
            {"name": "customer_rfm", "rows": customer_list[:100]},
        ],
        meta={"availability": availability.model_dump()},
    )


async def get_cohort_analysis(db: AsyncSession, business_id: int) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.customers or not availability.orders:
        return AnalyticsResponse(
            kpis=[KPICard(key="cohorts", label="Cohort Analysis", value="N/A", unavailable_reason="Requires customer purchase history.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    # First purchase per customer
    first_orders = await db.execute(
        select(
            Order.customer_id,
            func.min(Order.order_date).label("first_date"),
        )
        .where(Order.business_id == business_id, Order.customer_id.isnot(None))
        .group_by(Order.customer_id)
    )
    first_map = {row[0]: row[1] for row in first_orders.all()}

    # All orders
    all_orders = await db.execute(
        select(Order.customer_id, Order.order_date, Order.total_amount)
        .where(Order.business_id == business_id, Order.customer_id.isnot(None))
    )

    cohorts: dict[str, dict[int, set[int]]] = {}
    cohort_sizes: dict[str, set[int]] = {}

    for cid, odate, amt in all_orders.all():
        if cid not in first_map or not odate or not first_map[cid]:
            continue
        fdate = first_map[cid]
        cohort_month = fdate.strftime("%Y-%m")
        order_month = odate.strftime("%Y-%m")

        # calculate month diff
        f_year, f_m = int(cohort_month[:4]), int(cohort_month[5:7])
        o_year, o_m = int(order_month[:4]), int(order_month[5:7])
        m_diff = (o_year - f_year) * 12 + (o_m - f_m)

        if cohort_month not in cohorts:
            cohorts[cohort_month] = {}
            cohort_sizes[cohort_month] = set()

        cohort_sizes[cohort_month].add(cid)

        if m_diff not in cohorts[cohort_month]:
            cohorts[cohort_month][m_diff] = set()
        cohorts[cohort_month][m_diff].add(cid)

    matrix = []
    sorted_cohorts = sorted(cohorts.keys())
    for c_month in sorted_cohorts[-12:]: # Last 12 months
        total = len(cohort_sizes[c_month])
        row = {"cohort": c_month, "size": total}
        for m in range(6): # Months 0..5
            retained = len(cohorts[c_month].get(m, set()))
            rate = round((retained / total) * 100, 1) if total > 0 else 0.0
            row[f"m{m}"] = rate
        matrix.append(row)

    return AnalyticsResponse(
        kpis=[KPICard(key="active_cohorts", label="Tracked Cohorts", value=len(matrix))],
        charts=[ChartSeries(name="cohort_retention", data=matrix)],
        tables=[{"name": "cohort_matrix", "rows": matrix}],
        meta={"availability": availability.model_dump()},
    )


async def get_conversion_funnel(db: AsyncSession, business_id: int) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.events:
        return AnalyticsResponse(
            kpis=[KPICard(key="funnel", label="Conversion Funnel", value="N/A", unavailable_reason="Conversion analytics require website event data.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    stages = ["session", "product_view", "add_to_cart", "checkout_started", "purchase"]
    labels = ["Sessions", "Product Views", "Add to Cart", "Checkout Started", "Purchase"]
    counts = []

    for stage in stages:
        res = await db.execute(
            select(func.count(func.distinct(WebsiteEvent.session_id))).where(
                WebsiteEvent.business_id == business_id,
                WebsiteEvent.event_type == stage,
            )
        )
        counts.append(res.scalar() or 0)

    funnel_data = []
    prev = counts[0] if counts and counts[0] > 0 else 1
    for label, count in zip(labels, counts):
        conv_rate = round((count / counts[0]) * 100, 1) if counts[0] > 0 else 0.0
        drop_rate = round(((prev - count) / prev) * 100, 1) if prev > 0 else 0.0
        funnel_data.append({
            "stage": label,
            "count": count,
            "conversion_rate": conv_rate,
            "dropoff_rate": drop_rate,
        })
        prev = count if count > 0 else prev

    return AnalyticsResponse(
        kpis=[
            KPICard(key="overall_conversion", label="Overall Conversion Rate", value=f"{funnel_data[-1]['conversion_rate']}%" if funnel_data else "0%", format="text"),
            KPICard(key="cart_abandonment", label="Cart Abandonment Rate", value=f"{round(100 - (counts[3]/counts[2]*100), 1)}%" if len(counts) > 3 and counts[2] > 0 else "N/A", format="text"),
        ],
        charts=[ChartSeries(name="conversion_funnel", data=funnel_data)],
        meta={"availability": availability.model_dump()},
    )


async def get_inventory_analytics(db: AsyncSession, business_id: int) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.inventory and not availability.products:
        return AnalyticsResponse(
            kpis=[KPICard(key="inventory", label="Inventory", value=0, unavailable_reason="Upload inventory or product data to view Inventory Analytics.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    result = await db.execute(
        select(Inventory, Product)
        .join(Product, Product.id == Inventory.product_id)
        .where(Inventory.business_id == business_id)
    )
    rows = []
    out_of_stock = critical = low = healthy = 0
    total_val = 0.0

    for inv, prod in result.all():
        stock = inv.stock_quantity
        reorder = inv.reorder_level or 10
        val = round(stock * (prod.cost_price or prod.price or 0), 2)
        total_val += val

        if stock <= 0:
            st = "out_of_stock"
            out_of_stock += 1
        elif stock <= math.ceil(reorder * 0.5):
            st = "critical"
            critical += 1
        elif stock <= reorder:
            st = "low"
            low += 1
        else:
            st = "healthy"
            healthy += 1

        rows.append({
            "product_id": prod.id,
            "product": prod.name,
            "sku": prod.sku or "N/A",
            "stock": stock,
            "reorder_level": reorder,
            "status": st,
            "inventory_value": val,
        })

    kpis = [
        KPICard(key="inventory_value", label="Total Inventory Value", value=round(total_val, 2), format="currency"),
        KPICard(key="out_of_stock", label="Out of Stock (🔴)", value=out_of_stock),
        KPICard(key="critical", label="Critical Stock (🟠)", value=critical),
        KPICard(key="low", label="Low Stock (🟡)", value=low),
        KPICard(key="healthy", label="Healthy Stock (🟢)", value=healthy),
    ]

    return AnalyticsResponse(
        kpis=kpis,
        charts=[ChartSeries(name="inventory_status", data=rows)],
        tables=[{"name": "inventory", "rows": rows}],
        meta={"availability": availability.model_dump()},
    )


async def get_returns_analytics(db: AsyncSession, business_id: int) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.returns:
        return AnalyticsResponse(
            kpis=[KPICard(key="returns", label="Returns Analytics", value=0, unavailable_reason="Upload returns data to activate Returns Analytics.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    result = await db.execute(
        select(
            Return.reason,
            func.count(Return.id).label("returns_count"),
            func.coalesce(func.sum(Return.quantity), 0).label("units"),
            func.coalesce(func.sum(Return.refund_amount), 0).label("refunds"),
        )
        .where(Return.business_id == business_id)
        .group_by(Return.reason)
    )

    by_reason = []
    total_ret = 0
    total_refund = 0.0
    for r in result.all():
        cnt = int(r.returns_count or 0)
        ref = float(r.refunds or 0)
        total_ret += cnt
        total_refund += ref
        by_reason.append({
            "reason": r.reason or "Unspecified",
            "count": cnt,
            "units": int(r.units or 0),
            "refund_amount": round(ref, 2),
        })

    kpis = [
        KPICard(key="total_returns", label="Total Returns", value=total_ret),
        KPICard(key="total_refunds", label="Total Refund Amount", value=round(total_refund, 2), format="currency"),
    ]

    return AnalyticsResponse(
        kpis=kpis,
        charts=[ChartSeries(name="returns_by_reason", data=by_reason)],
        tables=[{"name": "returns", "rows": by_reason}],
        meta={"availability": availability.model_dump()},
    )


async def get_marketing_analytics(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.marketing:
        return AnalyticsResponse(
            kpis=[KPICard(key="marketing", label="Marketing Analytics", value=0, unavailable_reason="Marketing spend data not uploaded.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    start, end = _default_date_range(filters)
    result = await db.execute(
        select(
            MarketingSpend.channel,
            func.sum(MarketingSpend.spend),
            func.sum(MarketingSpend.revenue),
            func.sum(MarketingSpend.conversions),
        )
        .where(
            MarketingSpend.business_id == business_id,
            MarketingSpend.date >= start,
            MarketingSpend.date <= end,
        )
        .group_by(MarketingSpend.channel)
    )

    rows = []
    total_spend = total_rev = 0.0
    total_conv = 0
    for chan, spend, rev, conv in result.all():
        s_f = float(spend or 0)
        r_f = float(rev or 0)
        c_i = int(conv or 0)
        total_spend += s_f
        total_rev += r_f
        total_conv += c_i
        roas = round(r_f / s_f, 2) if s_f > 0 else None
        cac = round(s_f / c_i, 2) if c_i > 0 else None
        rows.append({"channel": chan or "Other", "spend": round(s_f, 2), "revenue": round(r_f, 2), "conversions": c_i, "roas": roas, "cac": cac})

    tot_roas = round(total_rev / total_spend, 2) if total_spend > 0 else None
    tot_cac = round(total_spend / total_conv, 2) if total_conv > 0 else None

    kpis = [
        KPICard(key="total_spend", label="Total Spend", value=round(total_spend, 2), format="currency"),
        KPICard(key="attributed_revenue", label="Attributed Revenue", value=round(total_rev, 2), format="currency"),
        KPICard(key="roas", label="Blended ROAS", value=tot_roas if tot_roas else "N/A"),
        KPICard(key="cac", label="Customer Acquisition Cost (CAC)", value=tot_cac if tot_cac else "N/A", format="currency" if tot_cac else "text"),
    ]

    return AnalyticsResponse(kpis=kpis, charts=[ChartSeries(name="spend_by_channel", data=rows)], tables=[{"name": "marketing", "rows": rows}], meta={"availability": availability.model_dump()})


async def get_geographic_analytics(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    start, end = _default_date_range(filters)
    availability = await get_data_availability(db, business_id)

    res = await db.execute(
        select(
            func.coalesce(Customer.country, "Unknown").label("country"),
            func.coalesce(Customer.region, "Unknown").label("state"),
            func.coalesce(Customer.city, "Unknown").label("city"),
            func.sum(Order.total_amount).label("revenue"),
            func.count(Order.id).label("orders"),
            func.count(func.distinct(Customer.id)).label("customers"),
        )
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.business_id == business_id, Order.order_date >= start, Order.order_date <= end)
        .group_by(Customer.country, Customer.region, Customer.city)
        .order_by(desc("revenue"))
    )

    rows = []
    for r in res.all():
        rev = float(r.revenue or 0)
        ords = int(r.orders or 0)
        rows.append({
            "country": r.country,
            "state": r.state,
            "city": r.city,
            "revenue": round(rev, 2),
            "orders": ords,
            "customers": int(r.customers or 0),
            "aov": round(rev / ords, 2) if ords > 0 else 0.0,
        })

    return AnalyticsResponse(
        kpis=[KPICard(key="geographic_locations", label="Active Regions", value=len(rows))],
        charts=[ChartSeries(name="revenue_by_country", data=rows[:20])],
        tables=[{"name": "geography", "rows": rows}],
        meta={"availability": availability.model_dump()},
    )


async def get_profitability_analytics(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    start, end = _default_date_range(filters)
    availability = await get_data_availability(db, business_id)

    cur = await _sum_orders(db, business_id, start, end, filters)
    profit, has_cost = await _profit_estimate(db, business_id, start, end)

    margin = round((profit / cur["revenue"]) * 100, 1) if has_cost and cur["revenue"] > 0 else None

    kpis = [
        KPICard(key="gross_revenue", label="Gross Revenue", value=round(cur["revenue"], 2), format="currency"),
        KPICard(key="discounts", label="Discounts Given", value=round(cur["discounts"], 2), format="currency"),
        KPICard(key="estimated_cost", label="Estimated Product Costs", value=round(cur["revenue"] - profit, 2) if has_cost else "N/A", format="currency" if has_cost else "text", unavailable_reason=None if has_cost else "Cost data missing from products dataset."),
        KPICard(key="net_profit", label="Net Profit", value=round(profit, 2) if has_cost else "N/A", format="currency" if has_cost else "text", unavailable_reason=None if has_cost else "Requires product cost prices."),
        KPICard(key="profit_margin", label="Profit Margin", value=f"{margin}%" if margin is not None else "N/A", format="text"),
    ]

    return AnalyticsResponse(kpis=kpis, charts=[], meta={"availability": availability.model_dump(), "has_cost": has_cost})


async def get_pareto_analysis(db: AsyncSession, business_id: int) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.orders:
        return AnalyticsResponse(kpis=[], charts=[], meta={"availability": availability.model_dump()})

    # Product Pareto 80/20
    p_res = await db.execute(
        select(
            Product.name,
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label("revenue"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Product.business_id == business_id)
        .group_by(Product.name)
        .order_by(desc("revenue"))
    )

    p_rows = p_res.all()
    tot_rev = sum(float(r.revenue or 0) for r in p_rows)

    pareto_data = []
    running = 0.0
    for r in p_rows:
        rev = float(r.revenue or 0)
        running += rev
        pct = round((running / tot_rev) * 100, 1) if tot_rev > 0 else 0.0
        pareto_data.append({"product": r.name, "revenue": round(rev, 2), "cumulative_pct": pct})

    top_80_count = sum(1 for d in pareto_data if d["cumulative_pct"] <= 80.0) or 1

    kpis = [
        KPICard(key="total_products", label="Total Products", value=len(pareto_data)),
        KPICard(key="top_80_count", label="Products Generating 80% Revenue", value=f"{top_80_count} ({round(top_80_count/len(pareto_data)*100, 1) if pareto_data else 0}%)", format="text"),
    ]

    return AnalyticsResponse(
        kpis=kpis,
        charts=[ChartSeries(name="pareto_products", data=pareto_data[:20])],
        tables=[{"name": "pareto", "rows": pareto_data}],
        meta={"availability": availability.model_dump()},
    )


async def get_sales_forecasting(db: AsyncSession, business_id: int) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.orders:
        return AnalyticsResponse(
            kpis=[KPICard(key="forecast", label="Sales Forecast", value="N/A", unavailable_reason="Insufficient historical data for reliable forecasting.")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    # Fetch daily order totals
    is_sqlite = db.bind and db.bind.dialect.name == "sqlite"
    if is_sqlite:
        bucket = func.strftime("%Y-%m-%d", Order.order_date).label("period")
    else:
        bucket = func.date_trunc("day", Order.order_date).label("period")

    res = await db.execute(
        select(bucket, func.coalesce(func.sum(Order.total_amount), 0), func.count(Order.id))
        .where(Order.business_id == business_id)
        .group_by(bucket)
        .order_by(bucket)
    )

    history = []
    for row in res.all():
        period_str = str(row[0]) if row[0] else ""
        if isinstance(row[0], (datetime, date)):

            period_str = row[0].strftime("%Y-%m-%d")
        history.append({"period": period_str, "actual_revenue": round(float(row[1]), 2), "actual_orders": int(row[2])})


    if len(history) < 7:
        return AnalyticsResponse(
            kpis=[KPICard(key="forecast", label="Sales Forecast", value="Insufficient Data", unavailable_reason="Requires at least 7 days of historical order data.")],
            charts=[ChartSeries(name="historical_sales", data=history)],
            meta={"availability": availability.model_dump()},
        )

    # Simple Exponential Smoothing (SES) for trend forecasting
    revs = [h["actual_revenue"] for h in history]
    alpha = 0.3
    level = revs[0]
    for r in revs:
        level = alpha * r + (1 - alpha) * level

    avg_rev = sum(revs) / len(revs)
    variance = sum((r - avg_rev)**2 for r in revs) / len(revs)
    std_dev = math.sqrt(variance)

    last_date = datetime.strptime(history[-1]["period"], "%Y-%m-%d")
    forecast_points = []

    for i in range(1, 31): # 30 days forecast
        f_date = (last_date + timedelta(days=i)).strftime("%Y-%m-%d")
        f_val = max(0.0, round(level, 2))
        forecast_points.append({
            "period": f_date,
            "forecast_revenue": f_val,
            "upper_bound": round(f_val + 1.96 * std_dev, 2),
            "lower_bound": max(0.0, round(f_val - 1.96 * std_dev, 2)),
        })

    kpis = [
        KPICard(key="forecast_30d", label="Projected 30-Day Revenue", value=round(level * 30, 2), format="currency"),
        KPICard(key="daily_baseline", label="Forecasted Daily Baseline", value=round(level, 2), format="currency"),
    ]

    return AnalyticsResponse(
        kpis=kpis,
        charts=[
            ChartSeries(name="actual_sales", data=history[-60:]), # last 60 days
            ChartSeries(name="sales_forecast", data=forecast_points),
        ],
        meta={"availability": availability.model_dump()},
    )


async def get_dashboard_layout(db: AsyncSession, business_id: int, user_id: int) -> dict[str, Any]:
    res = await db.execute(
        select(DashboardLayout).where(DashboardLayout.business_id == business_id, DashboardLayout.user_id == user_id, DashboardLayout.is_default.is_(True))
    )
    layout = res.scalar_one_or_none()
    if layout and layout.layout_json:
        import json
        return json.loads(layout.layout_json)
    return {
        "visible_kpis": ["revenue", "net_revenue", "profit", "margin", "orders", "customers", "aov", "returning_rate", "units", "return_rate"],
        "visible_charts": ["revenue_over_time", "orders_over_time"],
    }


async def save_dashboard_layout(db: AsyncSession, business_id: int, user_id: int, layout_dict: dict[str, Any]) -> bool:
    import json
    res = await db.execute(
        select(DashboardLayout).where(DashboardLayout.business_id == business_id, DashboardLayout.user_id == user_id, DashboardLayout.is_default.is_(True))
    )
    layout = res.scalar_one_or_none()
    if layout:
        layout.layout_json = json.dumps(layout_dict)
    else:
        db.add(DashboardLayout(business_id=business_id, user_id=user_id, layout_name="default", layout_json=json.dumps(layout_dict), is_default=True))
    await db.flush()
    return True


async def get_profitability_deep_dive(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    start, end = _default_date_range(filters)
    availability = await get_data_availability(db, business_id)
    if not availability.orders:
        return AnalyticsResponse(
            kpis=[KPICard(key="contribution_margin", label="Contribution Margin", value=0, unavailable_reason="No order data available")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    # Order level aggregated revenues and costs
    cond = _order_filters(business_id, start, end, filters)
    res = await db.execute(
        select(
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(Order.subtotal), 0),
            func.coalesce(func.sum(Order.discount), 0),
            func.coalesce(func.sum(Order.shipping_cost), 0),
            func.coalesce(func.sum(Order.tax), 0),
            func.coalesce(func.sum(Order.payment_fee), 0),
            func.count(Order.id),
        ).where(cond)
    )
    total_rev, subtotal, discount, shipping, tax, payment_fee, order_count = res.one()

    # Returns sum
    ret_res = await db.execute(
        select(func.coalesce(func.sum(Return.refund_amount), 0))
        .where(Return.business_id == business_id, Return.return_date >= start, Return.return_date <= end)
    )
    refunds = float(ret_res.scalar() or 0)

    # COGS sum from OrderItems
    cogs_res = await db.execute(
        select(func.coalesce(func.sum(OrderItem.quantity * func.coalesce(OrderItem.unit_cost, Product.cost_price, 0)), 0))
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .outerjoin(Product, OrderItem.product_id == Product.id)
        .where(cond)
    )
    cogs = float(cogs_res.scalar() or 0)

    net_revenue = float(total_rev) - refunds
    gross_profit = net_revenue - cogs
    gross_margin_pct = round((gross_profit / net_revenue * 100), 1) if net_revenue > 0 else 0.0

    # True Contribution Margin = Net Revenue - COGS - Shipping Cost - Payment Fee
    contribution_margin = net_revenue - cogs - float(shipping) - float(payment_fee)
    contribution_margin_pct = round((contribution_margin / net_revenue * 100), 1) if net_revenue > 0 else 0.0

    # Ad Spend, MER & CAC
    ad_spend_res = await db.execute(
        select(func.coalesce(func.sum(MarketingSpend.spend), 0))
        .where(MarketingSpend.business_id == business_id, MarketingSpend.date >= start, MarketingSpend.date <= end)
    )
    total_ad_spend = float(ad_spend_res.scalar() or 0)

    mer = round(float(total_rev) / total_ad_spend, 2) if total_ad_spend > 0 else None

    # New customers count in period
    first_orders_subq = (
        select(Order.customer_id, func.min(Order.order_date).label("first_date"))
        .where(Order.business_id == business_id, Order.customer_id.isnot(None))
        .group_by(Order.customer_id)
        .subquery()
    )
    new_cust_res = await db.execute(
        select(func.count(first_orders_subq.c.customer_id))
        .where(first_orders_subq.c.first_date >= start, first_orders_subq.c.first_date <= end)
    )
    new_customers_count = int(new_cust_res.scalar() or 0)
    cac = round(total_ad_spend / new_customers_count, 2) if (total_ad_spend > 0 and new_customers_count > 0) else None

    # ROAS per channel
    channel_spend_res = await db.execute(
        select(
            MarketingSpend.channel,
            func.coalesce(func.sum(MarketingSpend.spend), 0),
            func.coalesce(func.sum(MarketingSpend.revenue), 0)
        )
        .where(MarketingSpend.business_id == business_id, MarketingSpend.date >= start, MarketingSpend.date <= end)
        .group_by(MarketingSpend.channel)
    )
    channel_roas_data = []
    for ch, spend_val, rev_val in channel_spend_res.all():
        ch_name = ch or "Direct/Organic"
        ch_spend = float(spend_val)
        ch_rev = float(rev_val)
        roas_val = round(ch_rev / ch_spend, 2) if ch_spend > 0 else None
        channel_roas_data.append({
            "channel": ch_name,
            "ad_spend": ch_spend,
            "attributed_revenue": ch_rev,
            "roas": roas_val,
        })

    kpis = [
        KPICard(key="contribution_margin", label="Contribution Margin", value=round(contribution_margin, 2), format="currency"),
        KPICard(key="contribution_margin_pct", label="Contribution Margin %", value=contribution_margin_pct, format="percent"),
        KPICard(key="cogs", label="Total Cost of Goods (COGS)", value=round(cogs, 2), format="currency"),
        KPICard(key="shipping_cost", label="Total Shipping Cost", value=round(float(shipping), 2), format="currency"),
        KPICard(key="payment_fee", label="Total Payment Fees", value=round(float(payment_fee), 2), format="currency"),
        KPICard(key="ad_spend", label="Total Marketing Ad Spend", value=round(total_ad_spend, 2), format="currency", unavailable_reason="Add manual ad spend if empty" if total_ad_spend == 0 else None),
        KPICard(key="mer", label="MER (Marketing Efficiency Ratio)", value=mer if mer is not None else "N/A", format="number" if mer is not None else "string", unavailable_reason="Add ad spend to see MER" if mer is None else None),
        KPICard(key="cac", label="CAC (Customer Acquisition Cost)", value=cac if cac is not None else "N/A", format="currency" if cac is not None else "string", unavailable_reason="Add ad spend to see CAC" if cac is None else None),
    ]

    breakdown_table = [
        {"metric": "Gross Revenue", "amount": round(float(total_rev), 2), "pct_revenue": 100.0},
        {"metric": "Discounts", "amount": -round(float(discount), 2), "pct_revenue": round(-float(discount)/float(total_rev)*100, 1) if float(total_rev)>0 else 0},
        {"metric": "Returns & Refunds", "amount": -round(refunds, 2), "pct_revenue": round(-refunds/float(total_rev)*100, 1) if float(total_rev)>0 else 0},
        {"metric": "Net Revenue", "amount": round(net_revenue, 2), "pct_revenue": round(net_revenue/float(total_rev)*100, 1) if float(total_rev)>0 else 0},
        {"metric": "COGS", "amount": -round(cogs, 2), "pct_revenue": round(-cogs/float(total_rev)*100, 1) if float(total_rev)>0 else 0},
        {"metric": "Shipping Costs", "amount": -round(float(shipping), 2), "pct_revenue": round(-float(shipping)/float(total_rev)*100, 1) if float(total_rev)>0 else 0},
        {"metric": "Payment Gateway Fees", "amount": -round(float(payment_fee), 2), "pct_revenue": round(-float(payment_fee)/float(total_rev)*100, 1) if float(total_rev)>0 else 0},
        {"metric": "Contribution Margin", "amount": round(contribution_margin, 2), "pct_revenue": contribution_margin_pct},
    ]

    return AnalyticsResponse(
        kpis=kpis,
        charts=[ChartSeries(name="channel_roas", data=channel_roas_data)],
        tables=breakdown_table,
        meta={"availability": availability.model_dump()},
    )


async def get_cohorts_and_ltv(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.orders:
        return AnalyticsResponse(
            kpis=[KPICard(key="repeat_rate", label="Repeat Purchase Rate", value=0, unavailable_reason="No order data available")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    # Fetch orders with customer info
    res = await db.execute(
        select(Order.id, Order.order_date, Order.total_amount, Customer.email, Order.customer_id)
        .outerjoin(Customer, Order.customer_id == Customer.id)
        .where(Order.business_id == business_id)
        .order_by(Order.order_date.asc())
    )
    orders = res.all()

    # Customer first purchase mapping & order lists
    cust_orders: dict[str, list[dict]] = {}
    for oid, odate, amt, email, cid in orders:
        c_key = email or f"cust_{cid or 'unknown'}"
        if c_key not in cust_orders:
            cust_orders[c_key] = []
        cust_orders[c_key].append({"order_id": oid, "date": odate, "amount": float(amt)})

    total_customers = len(cust_orders)
    repeat_customers = sum(1 for c in cust_orders.values() if len(c) > 1)
    repeat_rate = round((repeat_customers / total_customers * 100), 1) if total_customers > 0 else 0.0

    # Days between 1st and 2nd purchase
    gaps = []
    for c_orders in cust_orders.values():
        if len(c_orders) >= 2:
            gap_days = (c_orders[1]["date"] - c_orders[0]["date"]).days
            if gap_days >= 0:
                gaps.append(gap_days)
    avg_days_between = round(sum(gaps) / len(gaps), 1) if gaps else 0.0

    # Cohort retention matrix by acquisition month YYYY-MM
    cohorts_dict: dict[str, dict[str, Any]] = {}
    now_dt = datetime.now(timezone.utc)

    # Retention days tracking: 30, 60, 90, 180 days
    retention_counts = {30: 0, 60: 0, 90: 0, 180: 0}
    eligible_counts = {30: 0, 60: 0, 90: 0, 180: 0}

    for c_key, c_orders in cust_orders.items():
        first_dt = c_orders[0]["date"]
        acq_month = first_dt.strftime("%Y-%m")

        if acq_month not in cohorts_dict:
            cohorts_dict[acq_month] = {"cohort": acq_month, "size": 0, "months": {}}
        cohorts_dict[acq_month]["size"] += 1

        # Track subsequent month purchases
        for o in c_orders:
            o_dt = o["date"]
            # Month diff
            month_diff = (o_dt.year - first_dt.year) * 12 + (o_dt.month - first_dt.month)
            if month_diff not in cohorts_dict[acq_month]["months"]:
                cohorts_dict[acq_month]["months"][month_diff] = {"customers": set(), "revenue": 0.0}
            cohorts_dict[acq_month]["months"][month_diff]["customers"].add(c_key)
            cohorts_dict[acq_month]["months"][month_diff]["revenue"] += o["amount"]

        # Check retention windows
        days_since_first = (now_dt - first_dt.replace(tzinfo=timezone.utc if first_dt.tzinfo is None else first_dt.tzinfo)).days
        for d in [30, 60, 90, 180]:
            if days_since_first >= d:
                eligible_counts[d] += 1
                has_subsequent = any((o["date"] - first_dt).days >= 1 and (o["date"] - first_dt).days <= d for o in c_orders[1:])
                if has_subsequent:
                    retention_counts[d] += 1

    retention_curve_data = []
    for d in [30, 60, 90, 180]:
        rate = round((retention_counts[d] / eligible_counts[d] * 100), 1) if eligible_counts[d] > 0 else 0.0
        retention_curve_data.append({"day": f"{d} Days", "retention_rate": rate, "retained_customers": retention_counts[d], "eligible_cohort_size": eligible_counts[d]})

    cohort_rows = []
    for acq_month in sorted(cohorts_dict.keys()):
        c_data = cohorts_dict[acq_month]
        c_size = c_data["size"]
        row = {"cohort": acq_month, "size": c_size}
        for m in range(0, 12):
            if m in c_data["months"]:
                cust_cnt = len(c_data["months"][m]["customers"])
                rev_val = round(c_data["months"][m]["revenue"], 2)
                pct_val = round((cust_cnt / c_size * 100), 1) if c_size > 0 else 0.0
                row[f"m{m}"] = {"retained_pct": pct_val, "retained_customers": cust_cnt, "revenue": rev_val}
            else:
                row[f"m{m}"] = {"retained_pct": 0.0, "retained_customers": 0, "revenue": 0.0}
        cohort_rows.append(row)

    avg_ltv = round(sum(sum(o["amount"] for o in clist) for clist in cust_orders.values()) / total_customers, 2) if total_customers > 0 else 0.0

    kpis = [
        KPICard(key="repeat_rate", label="Repeat Purchase Rate", value=repeat_rate, format="percent"),
        KPICard(key="avg_days_between", label="Avg Days Between 1st & 2nd Order", value=avg_days_between, format="number"),
        KPICard(key="avg_ltv", label="Average Customer LTV", value=avg_ltv, format="currency"),
        KPICard(key="total_customers", label="Total Customer Base", value=total_customers, format="number"),
    ]

    return AnalyticsResponse(
        kpis=kpis,
        charts=[
            ChartSeries(name="retention_curve", data=retention_curve_data),
        ],
        tables=cohort_rows,
        meta={"availability": availability.model_dump()},
    )


async def get_product_journey(db: AsyncSession, business_id: int) -> AnalyticsResponse:
    availability = await get_data_availability(db, business_id)
    if not availability.orders:
        return AnalyticsResponse(
            kpis=[KPICard(key="journey", label="Product Journey", value=0, unavailable_reason="No order data available")],
            charts=[],
            meta={"availability": availability.model_dump()},
        )

    # Co-occurrence & Purchase Sequences
    res = await db.execute(
        select(Order.customer_id, Order.order_date, OrderItem.product_id, Product.name, Product.sku)
        .join(OrderItem, Order.id == OrderItem.order_id)
        .outerjoin(Product, OrderItem.product_id == Product.id)
        .where(Order.business_id == business_id, Order.customer_id.isnot(None), OrderItem.product_id.isnot(None))
        .order_by(Order.customer_id, Order.order_date.asc())
    )
    rows = res.all()

    cust_history: dict[int, list[dict]] = {}
    for cid, odate, pid, pname, sku in rows:
        if cid not in cust_history:
            cust_history[cid] = []
        cust_history[cid].append({"product_id": pid, "product_name": pname or sku or f"Product #{pid}", "date": odate})

    sequence_pairs: dict[tuple[str, str], int] = {}
    first_purchase_counts: dict[str, int] = {}

    for cid, items in cust_history.items():
        if not items:
            continue
        first_p = items[0]["product_name"]
        first_purchase_counts[first_p] = first_purchase_counts.get(first_p, 0) + 1

        # Check subsequent orders
        seen_first = {items[0]["product_id"]}
        for item in items[1:]:
            if item["product_id"] not in seen_first:
                pair = (first_p, item["product_name"])
                sequence_pairs[pair] = sequence_pairs.get(pair, 0) + 1

    top_sequences = []
    sorted_pairs = sorted(sequence_pairs.items(), key=lambda x: x[1], reverse=True)[:15]
    for (p1, p2), cnt in sorted_pairs:
        top_sequences.append({"first_product": p1, "next_product": p2, "co_purchase_count": cnt})

    top_entry_products = []
    sorted_entry = sorted(first_purchase_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for pname, cnt in sorted_entry:
        top_entry_products.append({"product_name": pname, "first_order_count": cnt})

    return AnalyticsResponse(
        kpis=[
            KPICard(key="multi_purchase_customers", label="Repeat Buyer Count", value=sum(1 for items in cust_history.values() if len(items) > 1), format="number"),
            KPICard(key="unique_pairs_identified", label="Unique Product Journey Sequences", value=len(sequence_pairs), format="number"),
        ],
        charts=[ChartSeries(name="top_entry_products", data=top_entry_products)],
        tables=top_sequences,
        meta={"availability": availability.model_dump()},
    )


async def get_sku_profitability(db: AsyncSession, business_id: int, filters: DateRangeFilter) -> AnalyticsResponse:
    start, end = _default_date_range(filters)
    availability = await get_data_availability(db, business_id)

    # Product-level contribution margin ranking
    res = await db.execute(
        select(
            Product.id,
            Product.name,
            Product.sku,
            Product.price,
            Product.cost_price,
            Product.stock,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label("gross_revenue"),
            func.coalesce(func.sum(OrderItem.quantity * func.coalesce(OrderItem.unit_cost, Product.cost_price, 0)), 0).label("cogs"),
        )
        .select_from(Product)
        .outerjoin(OrderItem, Product.id == OrderItem.product_id)
        .outerjoin(Order, OrderItem.order_id == Order.id)
        .where(Product.business_id == business_id)
        .group_by(Product.id, Product.name, Product.sku, Product.price, Product.cost_price, Product.stock)
        .order_by(desc("gross_revenue"))
    )

    items = res.all()
    product_rows = []

    for pid, pname, sku, price, cost_price, stock, units, rev, cogs in items:
        rev_val = float(rev)
        cogs_val = float(cogs)
        gross_profit = rev_val - cogs_val
        margin_pct = round((gross_profit / rev_val * 100), 1) if rev_val > 0 else 0.0
        
        # High Revenue Low Margin Warning: If revenue is high (> top 25%) but margin < 20%
        warning = None
        if rev_val > 1000 and margin_pct < 20.0:
            warning = "High Revenue, Low Profit Margin (<20%)"

        product_rows.append({
            "product_id": pid,
            "name": pname or sku or f"SKU #{pid}",
            "sku": sku or f"SKU-{pid}",
            "price": float(price or 0),
            "cost_price": float(cost_price or 0),
            "stock_quantity": int(stock or 0),
            "units_sold": int(units),
            "revenue": round(rev_val, 2),
            "cogs": round(cogs_val, 2),
            "contribution_margin": round(gross_profit, 2),
            "margin_pct": margin_pct,
            "profitability_warning": warning,
        })

    # Sort by contribution margin desc
    product_rows_sorted = sorted(product_rows, key=lambda x: x["contribution_margin"], reverse=True)

    return AnalyticsResponse(
        kpis=[
            KPICard(key="total_skus", label="Total Product SKUs", value=len(product_rows), format="number"),
            KPICard(key="low_margin_skus", label="Low-Margin Warning SKUs", value=sum(1 for p in product_rows if p["profitability_warning"]), format="number"),
        ],
        charts=[ChartSeries(name="top_contribution_skus", data=[{"name": p["name"], "contribution_margin": p["contribution_margin"], "revenue": p["revenue"]} for p in product_rows_sorted[:10]])],
        tables=product_rows_sorted,
        meta={"availability": availability.model_dump()},
    )


async def execute_custom_report(
    db: AsyncSession,
    business_id: int,
    metric: str,
    dimension: str,
    date_range_preset: str = "30d",
    chart_type: str = "bar",
    filters_dict: dict = None,
) -> AnalyticsResponse:
    days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
    days = days_map.get(date_range_preset, 30)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # Dynamic column mapping
    dim_column = {
        "category": Product.category_id,
        "sales_channel": Order.sales_channel,
        "region": Customer.region,
        "country": Customer.country,
        "payment_method": Order.payment_method,
    }.get(dimension, Order.sales_channel)

    dim_label = {
        "category": Category.name,
        "sales_channel": Order.sales_channel,
        "region": Customer.region,
        "country": Customer.country,
        "payment_method": Order.payment_method,
    }.get(dimension, Order.sales_channel)

    metric_expr = {
        "revenue": func.coalesce(func.sum(Order.total_amount), 0),
        "orders": func.count(Order.id),
        "aov": func.coalesce(func.avg(Order.total_amount), 0),
        "shipping": func.coalesce(func.sum(Order.shipping_cost), 0),
        "contribution_margin": func.coalesce(func.sum(Order.total_amount - Order.shipping_cost - Order.payment_fee), 0),
    }.get(metric, func.coalesce(func.sum(Order.total_amount), 0))

    query = (
        select(dim_label.label("dim_val"), metric_expr.label("metric_val"))
        .select_from(Order)
    )
    if dimension == "category":
        query = query.outerjoin(OrderItem, Order.id == OrderItem.order_id).outerjoin(Product, OrderItem.product_id == Product.id).outerjoin(Category, Product.category_id == Category.id)
    elif dimension in ["region", "country"]:
        query = query.outerjoin(Customer, Order.customer_id == Customer.id)

    query = (
        query.where(Order.business_id == business_id, Order.order_date >= start, Order.order_date <= end)
        .group_by(dim_label)
        .order_by(desc("metric_val"))
    )

    res = await db.execute(query)
    rows = res.all()

    report_data = []
    for d_val, m_val in rows:
        report_data.append({
            "dimension": str(d_val or "Unspecified"),
            "metric_value": round(float(m_val), 2),
        })

    return AnalyticsResponse(
        kpis=[
            KPICard(key="total_metric_value", label=f"Total {metric.replace('_', ' ').title()}", value=sum(d["metric_value"] for d in report_data), format="currency" if metric in ["revenue", "aov", "contribution_margin", "shipping"] else "number"),
        ],
        charts=[ChartSeries(name=f"{metric}_by_{dimension}", data=report_data)],
        tables=report_data,
        meta={"metric": metric, "dimension": dimension, "chart_type": chart_type},
    )


async def execute_ai_query(db: AsyncSession, business_id: int, query_str: str) -> dict[str, Any]:
    q_lower = query_str.lower()

    if "mer" in q_lower or "cac" in q_lower or "contribution" in q_lower or "margin" in q_lower or "loss" in q_lower:
        filters = DateRangeFilter()
        res = await get_profitability_deep_dive(db, business_id, filters)
        margin_kpi = next((k for k in res.kpis if k.key == "contribution_margin"), None)
        mer_kpi = next((k for k in res.kpis if k.key == "mer"), None)
        cac_kpi = next((k for k in res.kpis if k.key == "cac"), None)
        ans = f"Based on your underlying database data: Contribution Margin is {margin_kpi.value if margin_kpi else 'N/A'}, MER is {mer_kpi.value if mer_kpi else 'N/A'}, and CAC is {cac_kpi.value if cac_kpi else 'N/A'}."
        return {
            "query": query_str,
            "intent": "Profitability & MER/CAC Deep Dive",
            "answer": ans,
            "data": [k.model_dump() for k in res.kpis],
            "chart_type": "kpi_cards",
        }

    if "cohort" in q_lower or "ltv" in q_lower or "retention" in q_lower or "repeat" in q_lower:
        filters = DateRangeFilter()
        res = await get_cohorts_and_ltv(db, business_id, filters)
        rep_kpi = next((k for k in res.kpis if k.key == "repeat_rate"), None)
        ltv_kpi = next((k for k in res.kpis if k.key == "avg_ltv"), None)
        ans = f"Cohort analysis shows a Repeat Purchase Rate of {rep_kpi.value if rep_kpi else '0'}% and an average Customer LTV of INR {ltv_kpi.value if ltv_kpi else '0'}."
        return {
            "query": query_str,
            "intent": "Cohort Retention & LTV Analysis",
            "answer": ans,
            "data": res.tables[:10],
            "chart_type": "table",
        }

    if "product" in q_lower or "sku" in q_lower or "journey" in q_lower or "together" in q_lower:
        res = await get_sku_profitability(db, business_id, DateRangeFilter())
        top_sku = res.tables[0] if res.tables else None
        top_name = top_sku["name"] if top_sku else "None"
        top_margin = top_sku["contribution_margin"] if top_sku else 0
        ans = f"SKU Profitability Analysis: Top product by contribution margin is '{top_name}' with INR {top_margin} contribution profit."
        return {
            "query": query_str,
            "intent": "SKU Profitability & Product Journey",
            "answer": ans,
            "data": res.tables[:10],
            "chart_type": "table",
        }

    # Fallback default: Revenue & Overview
    res = await execute_custom_report(db, business_id, "revenue", "sales_channel")
    ans = f"Summary Query: Retrieved total revenue breakdown across sales channels for query '{query_str}'."
    return {
        "query": query_str,
        "intent": "Revenue & Sales Channel Breakdown",
        "answer": ans,
        "data": res.tables,
        "chart_type": "bar",
    }

