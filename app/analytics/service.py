import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import DailyAverage, DailySummary, MonthlyData, WeeklySummary
from app.meals.models import Meal


async def get_daily_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date,
    calorie_goal: int = 2100,
) -> DailySummary:
    """Aggregate nutritional data for a single day using SQL."""
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

    result = await db.execute(
        select(
            func.coalesce(func.sum(Meal.calories), 0).label("total_calories"),
            func.coalesce(func.sum(Meal.protein_g), 0).label("total_protein"),
            func.coalesce(func.sum(Meal.carbs_g), 0).label("total_carbs"),
            func.coalesce(func.sum(Meal.fat_g), 0).label("total_fat"),
            func.count(Meal.id).label("meal_count"),
        ).where(
            Meal.user_id == user_id,
            Meal.logged_at >= start,
            Meal.logged_at <= end,
        )
    )
    row = result.one()

    total_cal = float(row.total_calories)
    return DailySummary(
        date=target_date,
        total_calories=total_cal,
        total_protein=float(row.total_protein),
        total_carbs=float(row.total_carbs),
        total_fat=float(row.total_fat),
        meal_count=int(row.meal_count),
        calorie_goal=calorie_goal,
        goal_percentage=round((total_cal / calorie_goal * 100) if calorie_goal > 0 else 0, 1),
    )


async def get_weekly_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    week_start: date,
    calorie_goal: int = 2100,
) -> WeeklySummary:
    """Aggregate nutritional data for a 7-day week."""
    days: list[DailySummary] = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        summary = await get_daily_summary(db, user_id, day, calorie_goal)
        days.append(summary)

    active_days = [d for d in days if d.meal_count > 0]
    n = max(len(active_days), 1)

    return WeeklySummary(
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        daily_averages=DailyAverage(
            avg_calories=round(sum(d.total_calories for d in active_days) / n, 1),
            avg_protein=round(sum(d.total_protein for d in active_days) / n, 1),
            avg_carbs=round(sum(d.total_carbs for d in active_days) / n, 1),
            avg_fat=round(sum(d.total_fat for d in active_days) / n, 1),
        ),
        days=days,
    )


async def get_monthly_data(
    db: AsyncSession,
    user_id: uuid.UUID,
    year: int,
    month: int,
    calorie_goal: int = 2100,
) -> MonthlyData:
    """Aggregate nutritional data for an entire month."""
    from calendar import monthrange

    _, num_days = monthrange(year, month)
    days: list[DailySummary] = []

    for day_num in range(1, num_days + 1):
        d = date(year, month, day_num)
        if d > date.today():
            break
        summary = await get_daily_summary(db, user_id, d, calorie_goal)
        days.append(summary)

    active_days = [d for d in days if d.meal_count > 0]
    n = max(len(active_days), 1)

    return MonthlyData(
        month=f"{year:04d}-{month:02d}",
        days=days,
        monthly_avg_calories=round(sum(d.total_calories for d in active_days) / n, 1),
    )
