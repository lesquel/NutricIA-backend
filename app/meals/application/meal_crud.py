"""Use case: Save, list, get, delete meals."""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.meals.infrastructure.models import Meal
from app.meals.infrastructure.repository import (
    create_meal_record,
    get_daily_meals_query,
    get_meal_by_id_query,
    delete_meal_record,
    get_meal_dates_in_month_query,
)
from app.meals.presentation import MealCreate, MealResponse
from app.shared.infrastructure.url_utils import resolve_image_url


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


async def get_meal_dates_in_month(
    db: AsyncSession,
    user_id: uuid.UUID,
    month_start: date,
) -> list[date]:
    """Get distinct dates in a month with at least one meal."""
    return await get_meal_dates_in_month_query(db, user_id, month_start)


def meal_to_response(meal: Meal, base_url: str = "") -> MealResponse:
    """Convert Meal model to response schema.

    When *base_url* is provided, ``image_url`` is resolved to an absolute URL.
    """
    image_url = (
        resolve_image_url(meal.image_url, base_url) if base_url else meal.image_url
    )
    return MealResponse(
        id=str(meal.id),
        name=meal.name,
        image_url=image_url,
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
