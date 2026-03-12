"""Tests for meal CRUD operations."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import User
from app.meals.application.meal_crud import (
    get_meal,
    list_meals,
    remove_meal,
    save_meal,
)
from app.meals.presentation import MealCreate


@pytest.mark.asyncio
async def test_save_meal_creates_meal(db_session: AsyncSession, test_user: User):
    """Test that saving a meal creates the meal in the database."""
    data = MealCreate(
        name="Chicken Salad",
        calories=350,
        protein_g=30,
        carbs_g=15,
        fat_g=18,
        meal_type="lunch",
    )

    meal = await save_meal(db_session, test_user.id, data)

    assert meal.id is not None
    assert meal.name == "Chicken Salad"
    assert meal.calories == 350
    assert meal.protein_g == 30
    assert meal.carbs_g == 15
    assert meal.fat_g == 18
    assert meal.meal_type == "lunch"
    assert meal.user_id == test_user.id


@pytest.mark.asyncio
async def test_save_meal_with_macros(db_session: AsyncSession, test_user: User):
    """Test saving a meal with macronutrients and tags."""
    data = MealCreate(
        name="Protein Bowl",
        calories=600,
        protein_g=45,
        carbs_g=50,
        fat_g=22,
        meal_type="dinner",
        tags=["high-protein", "low-carb"],
    )

    meal = await save_meal(db_session, test_user.id, data)

    assert meal.name == "Protein Bowl"
    assert len(meal.tags) == 2
    tag_labels = [tag.label for tag in meal.tags]
    assert "high-protein" in tag_labels
    assert "low-carb" in tag_labels


@pytest.mark.asyncio
async def test_list_meals_returns_user_meals_only(
    db_session: AsyncSession, test_user: User
):
    """Test that listing meals only returns meals for the specific user."""
    other_user_id = uuid.uuid4()

    data1 = MealCreate(
        name="Breakfast",
        calories=300,
        protein_g=10,
        carbs_g=40,
        fat_g=8,
        meal_type="breakfast",
    )
    data2 = MealCreate(
        name="Lunch",
        calories=500,
        protein_g=25,
        carbs_g=60,
        fat_g=15,
        meal_type="lunch",
    )

    meal1 = await save_meal(db_session, test_user.id, data1)
    meal2 = await save_meal(db_session, test_user.id, data2)
    await save_meal(db_session, other_user_id, data1)

    today = date.today()
    meals = await list_meals(db_session, test_user.id, today)

    assert len(meals) == 2
    meal_names = [m.name for m in meals]
    assert "Breakfast" in meal_names
    assert "Lunch" in meal_names


@pytest.mark.asyncio
async def test_list_meals_empty_for_new_user(db_session: AsyncSession):
    """Test that listing meals returns empty list for user with no meals."""
    new_user_id = uuid.uuid4()
    today = date.today()

    meals = await list_meals(db_session, new_user_id, today)

    assert meals == []


@pytest.mark.asyncio
async def test_get_meal_returns_correct_meal(db_session: AsyncSession, test_user: User):
    """Test getting a specific meal by ID returns the correct meal."""
    data = MealCreate(
        name="Snack", calories=150, protein_g=5, carbs_g=20, fat_g=5, meal_type="snack"
    )

    created_meal = await save_meal(db_session, test_user.id, data)

    retrieved_meal = await get_meal(db_session, test_user.id, created_meal.id)

    assert retrieved_meal is not None
    assert retrieved_meal.id == created_meal.id
    assert retrieved_meal.name == "Snack"


@pytest.mark.asyncio
async def test_get_meal_not_found_raises_error(
    db_session: AsyncSession, test_user: User
):
    """Test getting a non-existent meal returns None."""
    fake_id = uuid.uuid4()

    result = await get_meal(db_session, test_user.id, fake_id)

    assert result is None


@pytest.mark.asyncio
async def test_remove_meal_deletes_meal(db_session: AsyncSession, test_user: User):
    """Test removing a meal deletes it from the database."""
    data = MealCreate(
        name="To Delete",
        calories=100,
        protein_g=5,
        carbs_g=10,
        fat_g=3,
        meal_type="snack",
    )

    meal = await save_meal(db_session, test_user.id, data)
    meal_id = meal.id

    await remove_meal(db_session, meal)

    deleted_meal = await get_meal(db_session, test_user.id, meal_id)
    assert deleted_meal is None


@pytest.mark.asyncio
async def test_remove_meal_not_found_raises_error(
    db_session: AsyncSession, test_user: User
):
    """Test that removing a meal that was already deleted works without error."""
    from app.meals.infrastructure.repository import get_meal_by_id_query

    fake_meal_id = uuid.uuid4()

    result = await get_meal_by_id_query(db_session, test_user.id, fake_meal_id)
    assert result is None
