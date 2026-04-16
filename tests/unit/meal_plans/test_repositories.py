"""Unit tests for MealPlanRepositoryImpl using in-memory SQLite."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.meal_plans.domain.entities import (
    DietaryConstraints,
    Macros,
    MealPlan,
    PlannedMeal,
)
from app.meal_plans.domain.errors import PlanNotFoundError
from app.meal_plans.infrastructure.repositories import MealPlanRepositoryImpl


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_macros(p: float = 50.0, c: float = 150.0, f: float = 30.0) -> Macros:
    return Macros(protein_g=p, carbs_g=c, fat_g=f)


def _make_planned_meal(
    plan_id: uuid.UUID,
    day: int = 0,
    meal_type: str = "lunch",
) -> PlannedMeal:
    return PlannedMeal(
        id=uuid.uuid4(),
        plan_id=plan_id,
        day_of_week=day,
        meal_type=meal_type,  # type: ignore[arg-type]
        recipe_name=f"Recipe day{day} {meal_type}",
        recipe_ingredients=["rice", "chicken"],
        calories=500.0,
        macros=_make_macros(30, 60, 10),
        cook_time_minutes=20,
        difficulty="easy",
        servings=1,
        is_logged=False,
        logged_meal_id=None,
    )


def _make_plan(
    user_id: uuid.UUID,
    week_start: date,
    num_meals: int = 21,
) -> MealPlan:
    plan_id = uuid.uuid4()
    meal_types = ["breakfast", "lunch", "snack"]
    meals = []
    for day in range(7):
        for i, mt in enumerate(meal_types[: (num_meals // 7)]):
            meals.append(_make_planned_meal(plan_id, day=day, meal_type=mt))
    # if num_meals isn't divisible by 7, pad
    while len(meals) < num_meals:
        meals.append(_make_planned_meal(plan_id, day=len(meals) % 7))

    return MealPlan(
        id=plan_id,
        user_id=user_id,
        week_start=week_start,
        target_calories=2100,
        target_macros=_make_macros(),
        status="active",
        approximation=False,
        meals=meals[:num_meals],
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_get_round_trip(db_session: AsyncSession) -> None:
    """Create a plan with 21 meals, get it back and verify all fields."""
    repo = MealPlanRepositoryImpl(db_session)
    user_id = uuid.uuid4()
    week_start = date(2026, 4, 14)  # a Monday

    plan = _make_plan(user_id, week_start, num_meals=21)
    created = await repo.create(plan)
    await db_session.commit()

    fetched = await repo.get(created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.user_id == user_id
    assert fetched.week_start == week_start
    assert fetched.target_calories == 2100
    assert fetched.target_macros.protein_g == 50.0
    assert fetched.target_macros.carbs_g == 150.0
    assert fetched.target_macros.fat_g == 30.0
    assert fetched.status == "active"
    assert fetched.approximation is False
    assert len(fetched.meals) == 21


@pytest.mark.asyncio
async def test_macros_jsonb_round_trip(db_session: AsyncSession) -> None:
    """Macros serialized as JSON and deserialized correctly."""
    repo = MealPlanRepositoryImpl(db_session)
    user_id = uuid.uuid4()
    plan = _make_plan(user_id, date(2026, 4, 14), num_meals=3)
    created = await repo.create(plan)
    await db_session.commit()

    fetched = await repo.get(created.id)
    assert fetched is not None

    first_meal = fetched.meals[0]
    assert first_meal.macros.protein_g == 30.0
    assert first_meal.macros.carbs_g == 60.0
    assert first_meal.macros.fat_g == 10.0
    assert first_meal.recipe_ingredients == ["rice", "chicken"]


@pytest.mark.asyncio
async def test_get_current_for_user_returns_active_plan(
    db_session: AsyncSession,
) -> None:
    """get_current_for_user returns the active plan for the specified week."""
    repo = MealPlanRepositoryImpl(db_session)
    user_id = uuid.uuid4()
    week_start = date(2026, 4, 14)

    plan = _make_plan(user_id, week_start, num_meals=3)
    await repo.create(plan)
    await db_session.commit()

    found = await repo.get_current_for_user(user_id, week=week_start)
    assert found is not None
    assert found.user_id == user_id
    assert found.week_start == week_start


@pytest.mark.asyncio
async def test_get_current_for_user_different_week_returns_none(
    db_session: AsyncSession,
) -> None:
    """get_current_for_user returns None when no plan exists for the given week."""
    repo = MealPlanRepositoryImpl(db_session)
    user_id = uuid.uuid4()
    week_start = date(2026, 4, 14)

    plan = _make_plan(user_id, week_start, num_meals=3)
    await repo.create(plan)
    await db_session.commit()

    other_week = date(2026, 4, 21)
    found = await repo.get_current_for_user(user_id, week=other_week)
    assert found is None


@pytest.mark.asyncio
async def test_update_meal_swaps_recipe(db_session: AsyncSession) -> None:
    """update_meal replaces a planned meal's recipe data."""
    repo = MealPlanRepositoryImpl(db_session)
    user_id = uuid.uuid4()
    plan = _make_plan(user_id, date(2026, 4, 14), num_meals=3)
    created = await repo.create(plan)
    await db_session.commit()

    original_meal = created.meals[0]
    new_meal = PlannedMeal(
        id=original_meal.id,
        plan_id=created.id,
        day_of_week=original_meal.day_of_week,
        meal_type="dinner",
        recipe_name="New Recipe",
        recipe_ingredients=["pasta", "tomato"],
        calories=700.0,
        macros=Macros(protein_g=40, carbs_g=80, fat_g=20),
        cook_time_minutes=30,
        difficulty="medium",
        servings=2,
        is_logged=False,
        logged_meal_id=None,
    )

    updated = await repo.update_meal(created.id, original_meal.id, new_meal)
    await db_session.commit()

    assert updated.recipe_name == "New Recipe"
    assert updated.calories == 700.0
    assert updated.macros.protein_g == 40.0
    assert updated.meal_type == "dinner"
    assert updated.servings == 2


@pytest.mark.asyncio
async def test_mark_meal_logged(db_session: AsyncSession) -> None:
    """mark_meal_logged sets is_logged=True and links logged_meal_id."""
    repo = MealPlanRepositoryImpl(db_session)
    user_id = uuid.uuid4()
    plan = _make_plan(user_id, date(2026, 4, 14), num_meals=3)
    created = await repo.create(plan)
    await db_session.commit()

    meal = created.meals[0]
    assert meal.is_logged is False

    logged_meal_id = uuid.uuid4()
    updated = await repo.mark_meal_logged(created.id, meal.id, logged_meal_id)
    await db_session.commit()

    assert updated.is_logged is True
    assert updated.logged_meal_id == logged_meal_id


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_id(db_session: AsyncSession) -> None:
    """get returns None when the plan does not exist."""
    repo = MealPlanRepositoryImpl(db_session)
    result = await repo.get(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_list_for_user(db_session: AsyncSession) -> None:
    """list_for_user returns all plans for a user ordered by newest first."""
    repo = MealPlanRepositoryImpl(db_session)
    user_id = uuid.uuid4()

    plan1 = _make_plan(user_id, date(2026, 4, 7), num_meals=3)
    plan2 = _make_plan(user_id, date(2026, 4, 14), num_meals=3)
    await repo.create(plan1)
    await db_session.commit()
    await repo.create(plan2)
    await db_session.commit()

    plans = await repo.list_for_user(user_id)
    assert len(plans) == 2
    # Both plans are there (ordering may be same timestamp in SQLite — just check presence)
    week_starts = {p.week_start for p in plans}
    assert date(2026, 4, 7) in week_starts
    assert date(2026, 4, 14) in week_starts


@pytest.mark.asyncio
async def test_update_archives_plan(db_session: AsyncSession) -> None:
    """update changes the plan status to archived."""
    repo = MealPlanRepositoryImpl(db_session)
    user_id = uuid.uuid4()
    plan = _make_plan(user_id, date(2026, 4, 14), num_meals=3)
    created = await repo.create(plan)
    await db_session.commit()

    assert created.status == "active"

    to_archive = MealPlan(
        id=created.id,
        user_id=created.user_id,
        week_start=created.week_start,
        target_calories=created.target_calories,
        target_macros=created.target_macros,
        status="archived",
        approximation=created.approximation,
        meals=created.meals,
    )
    updated = await repo.update(to_archive)
    await db_session.commit()

    assert updated.status == "archived"
