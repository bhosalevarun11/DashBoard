from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.engine import (
    get_category_analytics,
    get_cohort_analysis,
    get_conversion_funnel,
    get_customer_analytics,
    get_data_availability,
    get_executive_dashboard,
    get_geographic_analytics,
    get_inventory_analytics,
    get_marketing_analytics,
    get_pareto_analysis,
    get_product_analytics,
    get_profitability_analytics,
    get_rfm_analysis,
    get_returns_analytics,
    get_sales_analytics,
    get_sales_forecasting,
    get_dashboard_layout,
    save_dashboard_layout,
    get_profitability_deep_dive,
    get_cohorts_and_ltv,
    get_product_journey,
    get_sku_profitability,
    execute_custom_report,
    execute_ai_query,
    invalidate_analytics_cache,
)
from app.analytics.insights import generate_alerts, generate_insights
from app.core.deps import get_current_user, get_verified_business
from app.database.session import get_db
from app.models import Alert, Insight, Order, Product, Customer, User, MarketingSpend
from app.reports.pdf_generator import generate_business_pdf_report
from app.schemas import (
    AlertResponse,
    AnalyticsResponse,
    DataAvailability,
    DateRangeFilter,
    InsightResponse,
    DashboardLayoutSave,
    AdSpendCreate,
    AdSpendResponse,
    AIQueryRequest,
    AIQueryResponse,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/availability/{business_id}", response_model=DataAvailability)
async def availability(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_data_availability(db, business_id)


@router.post("/dashboard/{business_id}", response_model=AnalyticsResponse)
async def dashboard(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_executive_dashboard(db, business_id, filters)


@router.post("/sales/{business_id}", response_model=AnalyticsResponse)
async def sales(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_sales_analytics(db, business_id, filters)


@router.post("/products/{business_id}", response_model=AnalyticsResponse)
async def products(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_product_analytics(db, business_id, filters)


@router.post("/categories/{business_id}", response_model=AnalyticsResponse)
async def categories(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_category_analytics(db, business_id, filters)


@router.post("/customers/{business_id}", response_model=AnalyticsResponse)
async def customers(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_customer_analytics(db, business_id, filters)


@router.get("/rfm/{business_id}", response_model=AnalyticsResponse)
async def rfm(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_rfm_analysis(db, business_id)


@router.get("/cohorts/{business_id}", response_model=AnalyticsResponse)
async def cohorts(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_cohort_analysis(db, business_id)


@router.get("/inventory/{business_id}", response_model=AnalyticsResponse)
async def inventory(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_inventory_analytics(db, business_id)


@router.get("/returns/{business_id}", response_model=AnalyticsResponse)
async def returns_analytics(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_returns_analytics(db, business_id)


@router.get("/funnel/{business_id}", response_model=AnalyticsResponse)
async def funnel(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_conversion_funnel(db, business_id)


@router.post("/marketing/{business_id}", response_model=AnalyticsResponse)
async def marketing(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_marketing_analytics(db, business_id, filters)


@router.post("/geography/{business_id}", response_model=AnalyticsResponse)
async def geography(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_geographic_analytics(db, business_id, filters)


@router.post("/profitability/{business_id}", response_model=AnalyticsResponse)
async def profitability(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_profitability_analytics(db, business_id, filters)


@router.get("/pareto/{business_id}", response_model=AnalyticsResponse)
async def pareto(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_pareto_analysis(db, business_id)


@router.get("/forecast/{business_id}", response_model=AnalyticsResponse)
async def forecast(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_sales_forecasting(db, business_id)


@router.post("/insights/{business_id}/generate", response_model=list[InsightResponse])
async def run_insights(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await generate_insights(db, business_id)


@router.get("/insights/{business_id}", response_model=list[InsightResponse])
async def list_insights(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    result = await db.execute(
        select(Insight).where(Insight.business_id == business_id).order_by(Insight.created_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.post("/alerts/{business_id}/generate", response_model=list[AlertResponse])
async def run_alerts(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await generate_alerts(db, business_id)


@router.get("/alerts/{business_id}", response_model=list[AlertResponse])
async def list_alerts(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    result = await db.execute(
        select(Alert).where(Alert.business_id == business_id, Alert.is_dismissed.is_(False))
        .order_by(Alert.created_at.desc()).limit(100)
    )
    return result.scalars().all()


@router.post("/alerts/{business_id}/{alert_id}/dismiss")
async def dismiss_alert(
    business_id: int,
    alert_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    res = await db.execute(select(Alert).where(Alert.id == alert_id, Alert.business_id == business_id))
    alert = res.scalar_one_or_none()
    if alert:
        alert.is_dismissed = True
        await db.flush()
    return {"success": True}


@router.get("/orders/{business_id}")
async def list_orders(
    business_id: int,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    safe_limit = min(max(1, limit), 200)
    safe_offset = max(0, offset)

    count_res = await db.execute(select(func.count(Order.id)).where(Order.business_id == business_id))
    total_count = count_res.scalar() or 0

    result = await db.execute(
        select(Order).where(Order.business_id == business_id).order_by(Order.order_date.desc()).offset(safe_offset).limit(safe_limit)
    )
    orders = result.scalars().all()
    items = [
        {
            "id": o.id,
            "order_date": o.order_date.strftime("%Y-%m-%d %H:%M") if o.order_date else "",
            "customer_id": o.customer_id,
            "status": o.status,
            "total_amount": o.total_amount,
            "discount": o.discount,
            "shipping_cost": o.shipping_cost,
            "tax": o.tax,
            "payment_method": o.payment_method or "N/A",
            "sales_channel": o.sales_channel or "Direct",
        }
        for o in orders
    ]
    return {
        "items": items,
        "total": total_count,
        "limit": safe_limit,
        "offset": safe_offset,
    }


@router.get("/layout/{business_id}")
async def get_layout(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_dashboard_layout(db, business_id, user.id)


@router.post("/layout/{business_id}")
async def save_layout(
    business_id: int,
    payload: DashboardLayoutSave,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    await save_dashboard_layout(db, business_id, user.id, payload.layout)
    return {"success": True}


@router.post("/reports/{business_id}/pdf")
async def export_pdf_report(
    business_id: int,
    report_type: str = "monthly",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    biz = await get_verified_business(business_id, user, db)
    filters = DateRangeFilter()

    # Route report generation based on report_type
    r_type = report_type.lower()
    if r_type == "sales":
        dash = await get_sales_analytics(db, business_id, filters)
        title = "Sales Performance Report"
    elif r_type in ("product", "products"):
        dash = await get_product_analytics(db, business_id, filters)
        title = "Product Analytics Report"
    elif r_type in ("customer", "customers"):
        dash = await get_customer_analytics(db, business_id, filters)
        title = "Customer Analytics & Segmentation Report"
    elif r_type == "inventory":
        dash = await get_inventory_analytics(db, business_id)
        title = "Inventory Valuation & Stock Risk Report"
    elif r_type in ("profitability", "profit"):
        dash = await get_profitability_analytics(db, business_id, filters)
        title = "Profitability & Margin Analysis Report"
    elif r_type == "returns":
        dash = await get_returns_analytics(db, business_id)
        title = "Returns & Refunds Analysis Report"
    else:
        dash = await get_executive_dashboard(db, business_id, filters)
        title = "Executive Business Performance Overview"

    kpis = [{"label": k.label, "value": k.value, "format": k.format} for k in dash.kpis]
    headers = ["Metric / Dimension", "Value"]
    rows = []
    for k in dash.kpis:
        val_display = "—" if k.value is None else str(k.value)
        rows.append([k.label, val_display])

    # Include detailed table data if present
    if dash.tables and len(dash.tables) > 0:
        first_tbl = dash.tables[0]
        tbl_rows = first_tbl.get("rows") if isinstance(first_tbl, dict) else getattr(first_tbl, "rows", None)
        if tbl_rows:
            sample_keys = list(tbl_rows[0].keys())[:4]
            headers = [k.replace("_", " ").title() for k in sample_keys]
            rows = [[str(r.get(k, "—")) for k in sample_keys] for r in tbl_rows[:50]]

    insights_res = await db.execute(select(Insight).where(Insight.business_id == business_id).limit(5))
    insight_texts = [ins.title for ins in insights_res.scalars().all()]

    pdf_bytes = generate_business_pdf_report(
        business_name=biz.name,
        report_title=title,
        kpis=kpis,
        table_headers=headers,
        table_rows=rows,
        insights=insight_texts,
    )

    filename = f"{r_type}_report_{biz.name.lower().replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/profitability-deep-dive/{business_id}", response_model=AnalyticsResponse)
async def profitability_deep_dive(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_profitability_deep_dive(db, business_id, filters)


@router.post("/cohorts-ltv/{business_id}", response_model=AnalyticsResponse)
async def cohorts_ltv(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_cohorts_and_ltv(db, business_id, filters)


@router.get("/product-journey/{business_id}", response_model=AnalyticsResponse)
async def product_journey(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_product_journey(db, business_id)


@router.post("/sku-profitability/{business_id}", response_model=AnalyticsResponse)
async def sku_profitability(
    business_id: int,
    filters: DateRangeFilter = DateRangeFilter(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await get_sku_profitability(db, business_id, filters)


@router.post("/ad-spend/{business_id}", response_model=AdSpendResponse)
async def add_ad_spend(
    business_id: int,
    payload: AdSpendCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    record = MarketingSpend(
        business_id=business_id,
        channel=payload.channel,
        spend=payload.spend,
        date=payload.date,
        campaign=payload.campaign,
        source="manual_entry",
    )
    db.add(record)
    await db.flush()
    invalidate_analytics_cache(business_id)
    return record


@router.post("/custom-report/{business_id}", response_model=AnalyticsResponse)
async def build_custom_report(
    business_id: int,
    metric: str = "revenue",
    dimension: str = "sales_channel",
    date_range_preset: str = "30d",
    chart_type: str = "bar",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    return await execute_custom_report(db, business_id, metric, dimension, date_range_preset, chart_type)


@router.post("/ai-query/{business_id}", response_model=AIQueryResponse)
async def query_ai_assistant(
    business_id: int,
    payload: AIQueryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    res = await execute_ai_query(db, business_id, payload.query)
    return AIQueryResponse(**res)

