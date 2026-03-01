"""Use case: Nutritional analytics (daily, weekly, monthly).

Optimized to use aggregated SQL queries instead of N+1 sequential calls.
"""

import uuid
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.meals.infrastructure import Meal
from app.analytics.presentation import (
    DailyAverage,
    DailySummary,
    MonthlyData,
    WeeklySummary,
)


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
        goal_percentage=round(
            (total_cal / calorie_goal * 100) if calorie_goal > 0 else 0, 1
        ),
    )


async def get_weekly_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    week_start: date,
    calorie_goal: int = 2100,
) -> WeeklySummary:
    """Aggregate nutritional data for a 7-day week using a single query."""
    start_dt = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(
        week_start + timedelta(days=6), time.max, tzinfo=timezone.utc
    )

    # Single query: group by date, get per-day aggregates
    result = await db.execute(
        select(
            func.date(Meal.logged_at).label("day"),
            func.coalesce(func.sum(Meal.calories), 0).label("total_calories"),
            func.coalesce(func.sum(Meal.protein_g), 0).label("total_protein"),
            func.coalesce(func.sum(Meal.carbs_g), 0).label("total_carbs"),
            func.coalesce(func.sum(Meal.fat_g), 0).label("total_fat"),
            func.count(Meal.id).label("meal_count"),
        )
        .where(
            Meal.user_id == user_id,
            Meal.logged_at >= start_dt,
            Meal.logged_at <= end_dt,
        )
        .group_by(func.date(Meal.logged_at))
    )
    rows_by_date = {row.day: row for row in result.all()}

    days: list[DailySummary] = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        row = rows_by_date.get(day)
        if row:
            total_cal = float(row.total_calories)
            days.append(
                DailySummary(
                    date=day,
                    total_calories=total_cal,
                    total_protein=float(row.total_protein),
                    total_carbs=float(row.total_carbs),
                    total_fat=float(row.total_fat),
                    meal_count=int(row.meal_count),
                    calorie_goal=calorie_goal,
                    goal_percentage=round(
                        (total_cal / calorie_goal * 100) if calorie_goal > 0 else 0, 1
                    ),
                )
            )
        else:
            days.append(
                DailySummary(
                    date=day,
                    total_calories=0,
                    total_protein=0,
                    total_carbs=0,
                    total_fat=0,
                    meal_count=0,
                    calorie_goal=calorie_goal,
                    goal_percentage=0,
                )
            )

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
    """Aggregate nutritional data for an entire month using a single query."""
    _, num_days = monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = min(date(year, month, num_days), date.today())

    start_dt = datetime.combine(month_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(month_end, time.max, tzinfo=timezone.utc)

    # Single query: group by date
    result = await db.execute(
        select(
            func.date(Meal.logged_at).label("day"),
            func.coalesce(func.sum(Meal.calories), 0).label("total_calories"),
            func.coalesce(func.sum(Meal.protein_g), 0).label("total_protein"),
            func.coalesce(func.sum(Meal.carbs_g), 0).label("total_carbs"),
            func.coalesce(func.sum(Meal.fat_g), 0).label("total_fat"),
            func.count(Meal.id).label("meal_count"),
        )
        .where(
            Meal.user_id == user_id,
            Meal.logged_at >= start_dt,
            Meal.logged_at <= end_dt,
        )
        .group_by(func.date(Meal.logged_at))
    )
    rows_by_date = {row.day: row for row in result.all()}

    days: list[DailySummary] = []
    for day_num in range(1, num_days + 1):
        d = date(year, month, day_num)
        if d > date.today():
            break
        row = rows_by_date.get(d)
        if row:
            total_cal = float(row.total_calories)
            days.append(
                DailySummary(
                    date=d,
                    total_calories=total_cal,
                    total_protein=float(row.total_protein),
                    total_carbs=float(row.total_carbs),
                    total_fat=float(row.total_fat),
                    meal_count=int(row.meal_count),
                    calorie_goal=calorie_goal,
                    goal_percentage=round(
                        (total_cal / calorie_goal * 100) if calorie_goal > 0 else 0, 1
                    ),
                )
            )
        else:
            days.append(
                DailySummary(
                    date=d,
                    total_calories=0,
                    total_protein=0,
                    total_carbs=0,
                    total_fat=0,
                    meal_count=0,
                    calorie_goal=calorie_goal,
                    goal_percentage=0,
                )
            )

    active_days = [d for d in days if d.meal_count > 0]
    n = max(len(active_days), 1)

    return MonthlyData(
        month=f"{year:04d}-{month:02d}",
        days=days,
        monthly_avg_calories=round(sum(d.total_calories for d in active_days) / n, 1),
    )
