"""Meals infrastructure — Database repository."""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.meals.infrastructure import Meal, MealTag
from app.meals.presentation import MealCreate


async def create_meal_record(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: MealCreate,
) -> Meal:
    """Save a confirmed meal to the database."""
    meal = Meal(
        user_id=user_id,
        name=data.name,
        image_url=data.image_url,
        calories=data.calories,
        protein_g=data.protein_g,
        carbs_g=data.carbs_g,
        fat_g=data.fat_g,
        meal_type=data.meal_type,
        confidence_score=data.confidence_score,
        logged_at=data.logged_at or datetime.now(timezone.utc),
    )
    db.add(meal)
    await db.flush()

    # Add tags
    for tag_label in data.tags:
        tag = MealTag(meal_id=meal.id, label=tag_label)
        db.add(tag)

    await db.flush()
    await db.refresh(meal)
    return meal


async def get_daily_meals_query(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date,
) -> list[Meal]:
    """Get all meals for a user on a specific date."""
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

    result = await db.execute(
        select(Meal)
        .where(
            Meal.user_id == user_id,
            Meal.logged_at >= start,
            Meal.logged_at <= end,
        )
        .order_by(Meal.logged_at)
    )
    return list(result.scalars().all())


async def get_meal_by_id_query(
    db: AsyncSession,
    user_id: uuid.UUID,
    meal_id: uuid.UUID,
) -> Meal | None:
    """Get a single meal by ID, scoped to user."""
    result = await db.execute(
        select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_meal_record(
    db: AsyncSession,
    meal: Meal,
) -> None:
    """Delete a meal."""
    await db.delete(meal)


async def get_meal_dates_in_month_query(
    db: AsyncSession,
    user_id: uuid.UUID,
    month_start: date,
) -> list[date]:
    """Get distinct dates in a month where user has logged meals."""
    month_end = (
        date(month_start.year + 1, 1, 1)
        if month_start.month == 12
        else date(month_start.year, month_start.month + 1, 1)
    )
    start_dt = datetime.combine(month_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(month_end, time.min, tzinfo=timezone.utc)

    result = await db.execute(
        select(func.date(Meal.logged_at).label("meal_date"))
        .where(
            Meal.user_id == user_id,
            Meal.logged_at >= start_dt,
            Meal.logged_at < end_dt,
        )
        .group_by(func.date(Meal.logged_at))
        .order_by(func.date(Meal.logged_at))
    )

    return [row.meal_date for row in result]
