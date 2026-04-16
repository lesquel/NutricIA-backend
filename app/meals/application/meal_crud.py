"""Use case: Save, list, get, delete meals."""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.meals.infrastructure.models import Meal
from app.meals.infrastructure.repository import (
    create_meal_record,
    get_daily_meals_query,
    get_meal_by_id_query,
    delete_meal_record,
    get_meal_dates_in_month_query,
)
from app.meals.presentation import MealCreate, MealResponse, MealUpdate


async def save_meal(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: MealCreate,
) -> Meal:
    """Save a confirmed meal to the database."""
    return await create_meal_record(db, user_id, data)


async def list_meals(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date,
) -> list[Meal]:
    """Get all meals for a user on a specific date."""
    return await get_daily_meals_query(db, user_id, target_date)


async def get_meal(
    db: AsyncSession,
    user_id: uuid.UUID,
    meal_id: uuid.UUID,
) -> Meal | None:
    """Get a single meal by ID, scoped to user."""
    return await get_meal_by_id_query(db, user_id, meal_id)


async def remove_meal(
    db: AsyncSession,
    meal: Meal,
) -> None:
    """Delete a meal."""
    await delete_meal_record(db, meal)


async def list_meals_last_n_days(
    db: AsyncSession,
    user_id: uuid.UUID,
    days: int = 30,
) -> list[Meal]:
    """Get all meals for a user within the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Meal)
        .where(Meal.user_id == user_id, Meal.logged_at >= cutoff)
        .order_by(Meal.logged_at.desc())
    )
    return list(result.scalars().all())


async def get_meal_dates_in_month(
    db: AsyncSession,
    user_id: uuid.UUID,
    month_start: date,
) -> list[date]:
    """Get distinct dates in a month with at least one meal."""
    return await get_meal_dates_in_month_query(db, user_id, month_start)


async def update_meal(
    db: AsyncSession,
    meal: Meal,
    data: MealUpdate,
) -> Meal:
    """Apply partial updates to an existing meal."""
    if data.name is not None:
        meal.name = data.name
    if data.calories is not None:
        meal.calories = data.calories
    if data.protein_g is not None:
        meal.protein_g = data.protein_g
    if data.carbs_g is not None:
        meal.carbs_g = data.carbs_g
    if data.fat_g is not None:
        meal.fat_g = data.fat_g
    if data.meal_type is not None:
        meal.meal_type = data.meal_type
    if data.image_url is not None:
        meal.image_url = data.image_url

    await db.flush()
    await db.refresh(meal)
    return meal


def meal_to_response(meal: Meal) -> MealResponse:
    """Convert Meal model to response schema."""
    return MealResponse(
        id=str(meal.id),
        name=meal.name,
        image_url=meal.image_url,
        calories=meal.calories,
        protein_g=meal.protein_g,
        carbs_g=meal.carbs_g,
        fat_g=meal.fat_g,
        meal_type=meal.meal_type,
        confidence_score=meal.confidence_score,
        tags=[tag.label for tag in meal.tags],
        logged_at=meal.logged_at,
        created_at=meal.created_at,
    )
