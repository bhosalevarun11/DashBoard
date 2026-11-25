import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_verified_business
from app.database.session import get_db
from app.models import SavedCustomReport, ScheduledReport, User
from app.schemas import (
    SavedCustomReportCreate,
    SavedCustomReportResponse,
    ScheduledReportCreate,
    ScheduledReportResponse,
)

router = APIRouter(prefix="/reports-custom", tags=["custom_reports"])


@router.get("/saved/{business_id}", response_model=list[SavedCustomReportResponse])
async def list_saved_reports(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    res = await db.execute(
        select(SavedCustomReport)
        .where(SavedCustomReport.business_id == business_id, SavedCustomReport.user_id == user.id)
        .order_by(SavedCustomReport.created_at.desc())
    )
    return res.scalars().all()


@router.post("/saved/{business_id}", response_model=SavedCustomReportResponse)
async def create_saved_report(
    business_id: int,
    payload: SavedCustomReportCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    report = SavedCustomReport(
        business_id=business_id,
        user_id=user.id,
        name=payload.name,
        metric=payload.metric,
        dimension=payload.dimension,
        date_range_preset=payload.date_range_preset,
        chart_type=payload.chart_type,
        filters_json=json.dumps(payload.filters),
    )
    db.add(report)
    await db.flush()
    return report


@router.get("/schedules/{business_id}", response_model=list[ScheduledReportResponse])
async def list_scheduled_reports(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    res = await db.execute(
        select(ScheduledReport)
        .where(ScheduledReport.business_id == business_id)
        .order_by(ScheduledReport.created_at.desc())
    )
    return res.scalars().all()


@router.post("/schedules/{business_id}", response_model=ScheduledReportResponse)
async def create_scheduled_report(
    business_id: int,
    payload: ScheduledReportCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    schedule = ScheduledReport(
        business_id=business_id,
        name=payload.name,
        frequency=payload.frequency,
        recipient_email=payload.recipient_email,
        webhook_url=payload.webhook_url,
        is_active=payload.is_active,
    )
    db.add(schedule)
    await db.flush()
    return schedule
