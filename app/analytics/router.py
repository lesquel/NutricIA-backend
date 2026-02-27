from datetime import date

from fastapi import APIRouter

from app.analytics.schemas import DailySummary, MonthlyData, WeeklySummary
from app.analytics.service import get_daily_summary, get_monthly_data, get_weekly_summary
from app.dependencies import DB, CurrentUser

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/daily", response_model=DailySummary)
async def daily_analytics(
    user: CurrentUser,
    db: DB,
    target_date: date | None = None,
) -> DailySummary:
    """Get aggregated nutritional summary for a single day."""
    if target_date is None:
        target_date = date.today()
    return await get_daily_summary(db, user.id, target_date, user.calorie_goal)


@router.get("/weekly", response_model=WeeklySummary)
async def weekly_analytics(
    user: CurrentUser,
    db: DB,
    week_start: date | None = None,
) -> WeeklySummary:
    """Get aggregated nutritional summary for a 7-day week."""
    if week_start is None:
        today = date.today()
        week_start = today - __import__("datetime").timedelta(days=today.weekday())
    return await get_weekly_summary(db, user.id, week_start, user.calorie_goal)


@router.get("/monthly", response_model=MonthlyData)
async def monthly_analytics(
    user: CurrentUser,
    db: DB,
    year: int | None = None,
    month: int | None = None,
) -> MonthlyData:
    """Get aggregated nutritional data for a month."""
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
    return await get_monthly_data(db, user.id, year, month, user.calorie_goal)
