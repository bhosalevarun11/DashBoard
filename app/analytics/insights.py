from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.engine import (
    _profit_estimate,
    _sum_orders,
    get_data_availability,
    get_inventory_analytics,
)
from app.models import Alert, AlertSeverity, Insight, Order, Product, Return
from app.schemas import DateRangeFilter


async def generate_insights(db: AsyncSession, business_id: int) -> list[Insight]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    prev_start = start - timedelta(days=30)
    filters = DateRangeFilter()
    availability = await get_data_availability(db, business_id)
    insights: list[Insight] = []

    if availability.orders:
        current = await _sum_orders(db, business_id, start, end, filters)
        previous = await _sum_orders(db, business_id, prev_start, start, filters)

        if previous["revenue"] > 0:
            change = ((current["revenue"] - previous["revenue"]) / previous["revenue"]) * 100
            if change >= 5:
                insights.append(Insight(
                    business_id=business_id,
                    insight_type="revenue_growth",
                    title=f"Revenue increased {change:.1f}% compared with the previous period.",
                    description="Your business is showing positive revenue trajectory over the past 30 days.",
                    impact="Positive sales momentum and healthy demand.",
                    recommended_action="Analyze top-performing channels and double down on successful ad campaigns.",
                ))
            elif change <= -5:
                insights.append(Insight(
                    business_id=business_id,
                    insight_type="revenue_decline",
                    title=f"Revenue declined {abs(change):.1f}% compared with the previous period.",
                    description="Revenue dropped versus the prior 30-day period.",
                    impact="Risk of missing quarterly sales targets.",
                    recommended_action="Review underperforming product categories, discount strategies, and marketing spend.",
                ))

        profit, has_cost = await _profit_estimate(db, business_id, start, end)
        if has_cost and current["revenue"] > 0:
            margin = (profit / current["revenue"]) * 100
            if margin < 10:
                insights.append(Insight(
                    business_id=business_id,
                    insight_type="low_margin",
                    title=f"Overall profit margin is currently low at {margin:.1f}%.",
                    description="Product cost structure is narrowing gross profit margins.",
                    impact="High revenue volume without sufficient profit margins limits net cash flow.",
                    recommended_action="Review product pricing strategies, supplier costs, and shipping subsidies.",
                ))
            elif margin >= 30:
                insights.append(Insight(
                    business_id=business_id,
                    insight_type="high_margin",
                    title=f"Strong profit margin of {margin:.1f}% recorded.",
                    description="Your pricing model and product cost structure are yielding high profitability.",
                    impact="High financial efficiency and cash reserve generation.",
                    recommended_action="Reinvest profit into customer acquisition and expanding top-margin product lines.",
                ))

    if availability.inventory or availability.products:
        inv = await get_inventory_analytics(db, business_id)
        if inv.tables:
            for row in inv.tables[0]["rows"]:
                if row["status"] == "out_of_stock":
                    insights.append(Insight(
                        business_id=business_id,
                        insight_type="out_of_stock",
                        title=f"{row['product']} (SKU: {row['sku']}) is completely out of stock.",
                        description="Inventory level reached zero units.",
                        impact="Direct revenue loss and negative customer purchasing experience.",
                        recommended_action="Place urgent reorder with supplier or pause active ad campaigns for this SKU.",
                    ))
                elif row["status"] == "critical":
                    insights.append(Insight(
                        business_id=business_id,
                        insight_type="low_stock",
                        title=f"{row['product']} has only {row['stock']} units remaining.",
                        description="Stock quantity is below 50% of the reorder threshold.",
                        impact="Imminent risk of stockout within days.",
                        recommended_action="Review supplier lead times and issue purchase orders immediately.",
                    ))

    if availability.returns:
        ret_res = await db.execute(
            select(
                Product.name,
                func.count(Return.id).label("ret_count"),
            )
            .join(Product, Product.id == Return.product_id)
            .where(Return.business_id == business_id)
            .group_by(Product.name)
            .order_by(func.count(Return.id).desc())
            .limit(1)
        )
        top_ret = ret_res.first()
        if top_ret and top_ret[1] >= 3:
            insights.append(Insight(
                business_id=business_id,
                insight_type="high_return_product",
                title=f"Product '{top_ret[0]}' has a high return frequency ({top_ret[1]} returns).",
                description="This item represents a disproportionately high percentage of overall customer returns.",
                impact="Erodes profitability through return handling costs and customer dissatisfaction.",
                recommended_action="Inspect product quality, sizing guide accuracy, and packaging integrity.",
            ))

    for insight in insights:
        db.add(insight)
    await db.flush()
    return insights


async def generate_alerts(db: AsyncSession, business_id: int) -> list[Alert]:
    alerts: list[Alert] = []
    availability = await get_data_availability(db, business_id)

    if availability.inventory or availability.products:
        inv = await get_inventory_analytics(db, business_id)
        if inv.tables:
            for row in inv.tables[0]["rows"]:
                if row["status"] == "out_of_stock":
                    alerts.append(Alert(
                        business_id=business_id,
                        severity=AlertSeverity.critical,
                        title=f"🔴 Out of stock: {row['product']}",
                        message=f"SKU {row['sku']} has 0 units left in inventory.",
                        category="inventory",
                    ))
                elif row["status"] in ("critical", "low"):
                    alerts.append(Alert(
                        business_id=business_id,
                        severity=AlertSeverity.warning,
                        title=f"🟠 Low stock warning: {row['product']}",
                        message=f"Only {row['stock']} units remaining (reorder level: {row['reorder_level']}).",
                        category="inventory",
                    ))

    if availability.orders:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30)
        prev_start = start - timedelta(days=30)
        filters = DateRangeFilter()
        current = await _sum_orders(db, business_id, start, end, filters)
        previous = await _sum_orders(db, business_id, prev_start, start, filters)
        if previous["revenue"] > 0:
            change = ((current["revenue"] - previous["revenue"]) / previous["revenue"]) * 100
            if change >= 10:
                alerts.append(Alert(
                    business_id=business_id,
                    severity=AlertSeverity.positive,
                    title=f"🟢 Revenue Spike: +{change:.1f}% growth",
                    message="Total monthly revenue increased significantly compared to the prior period.",
                    category="sales",
                ))
            elif change <= -10:
                alerts.append(Alert(
                    business_id=business_id,
                    severity=AlertSeverity.warning,
                    title=f"🟠 Revenue Drop: -{abs(change):.1f}% decline",
                    message="Monthly revenue experienced a notable drop compared to the prior period.",
                    category="sales",
                ))

    for alert in alerts:
        db.add(alert)
    await db.flush()
    return alerts
