"""Unit tests for meal plan use cases — mocked repos and generator."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.meal_plans.application.generate_plan_use_case import GeneratePlanUseCase
from app.meal_plans.application.get_current_plan_use_case import GetCurrentPlanUseCase
from app.meal_plans.application.log_meal_use_case import LogMealUseCase
from app.meal_plans.application.swap_meal_use_case import SwapMealUseCase
from app.meal_plans.domain.entities import (
    DietaryConstraints,
    Macros,
    MealPlan,
    PlannedMeal,
)
from app.meal_plans.domain.errors import PlanNotFoundError


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_macros() -> Macros:
    return Macros(protein_g=50, carbs_g=150, fat_g=30)


def _make_constraints() -> DietaryConstraints:
    return DietaryConstraints(
        vegetarian=False, vegan=False, gluten_free=False, allergies=[]
    )


def _make_meal(plan_id: uuid.UUID, meal_id: uuid.UUID | None = None) -> PlannedMeal:
    return PlannedMeal(
        id=meal_id or uuid.uuid4(),
        plan_id=plan_id,
        day_of_week=0,
        meal_type="lunch",  # type: ignore[arg-type]
        recipe_name="Test Recipe",
        recipe_ingredients=["rice"],
        calories=500.0,
        macros=_make_macros(),
        cook_time_minutes=20,
        difficulty="easy",
        servings=1,
        is_logged=False,
        logged_meal_id=None,
    )


def _make_plan(
    user_id: uuid.UUID,
    status: str = "active",
    meals: list[PlannedMeal] | None = None,
) -> MealPlan:
    plan_id = uuid.uuid4()
    m = meals if meals is not None else [_make_meal(plan_id)]
    return MealPlan(
        id=plan_id,
        user_id=user_id,
        week_start=date(2026, 4, 14),
        target_calories=2100,
        target_macros=_make_macros(),
        status=status,  # type: ignore[arg-type]
        approximation=False,
        meals=m,
    )


# ── GeneratePlanUseCase ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_plan_no_existing_plan() -> None:
    """When no active plan exists, generator is called and plan is persisted."""
    user_id = uuid.uuid4()
    new_plan = _make_plan(user_id)

    repo = AsyncMock()
    repo.get_current_for_user = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=new_plan)

    generator = AsyncMock()
    generator.generate = AsyncMock(return_value=new_plan)

    uc = GeneratePlanUseCase(plan_repo=repo, generator=generator)
    result = await uc.execute(
        user_id=user_id,
        target_calories=2100,
        target_macros=_make_macros(),
        constraints=_make_constraints(),
        context={},
        week_start=date(2026, 4, 14),
    )

    assert result == new_plan
    repo.create.assert_called_once()
    generator.generate.assert_called_once()


@pytest.mark.asyncio
async def test_generate_plan_archives_existing_plan() -> None:
    """If an active plan exists for the week, it is archived before generating."""
    user_id = uuid.uuid4()
    existing = _make_plan(user_id, status="active")
    new_plan = _make_plan(user_id)

    repo = AsyncMock()
    repo.get_current_for_user = AsyncMock(return_value=existing)
    repo.update = AsyncMock(return_value=existing)
    repo.create = AsyncMock(return_value=new_plan)

    generator = AsyncMock()
    generator.generate = AsyncMock(return_value=new_plan)

    uc = GeneratePlanUseCase(plan_repo=repo, generator=generator)
    result = await uc.execute(
        user_id=user_id,
        target_calories=2100,
        target_macros=_make_macros(),
        constraints=_make_constraints(),
        context={},
        week_start=date(2026, 4, 14),
    )

    # update was called with archived status
    repo.update.assert_called_once()
    archived_plan = repo.update.call_args[0][0]
    assert archived_plan.status == "archived"
    assert result == new_plan


# ── GetCurrentPlanUseCase ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_plan_delegates_to_repo() -> None:
    """Returns whatever the repo returns for the user and week."""
    user_id = uuid.uuid4()
    plan = _make_plan(user_id)

    repo = AsyncMock()
    repo.get_current_for_user = AsyncMock(return_value=plan)

    uc = GetCurrentPlanUseCase(plan_repo=repo)
    result = await uc.execute(user_id=user_id, week=date(2026, 4, 14))

    assert result == plan
    repo.get_current_for_user.assert_called_once_with(user_id, week=date(2026, 4, 14))


@pytest.mark.asyncio
async def test_get_current_plan_defaults_to_today() -> None:
    """If week is not specified, today's date is used."""
    user_id = uuid.uuid4()

    repo = AsyncMock()
    repo.get_current_for_user = AsyncMock(return_value=None)

    uc = GetCurrentPlanUseCase(plan_repo=repo)
    result = await uc.execute(user_id=user_id)

    assert result is None
    call_kwargs = repo.get_current_for_user.call_args[1]
    assert "week" in call_kwargs


@pytest.mark.asyncio
async def test_get_current_plan_returns_none_when_not_found() -> None:
    """Returns None when no active plan exists."""
    repo = AsyncMock()
    repo.get_current_for_user = AsyncMock(return_value=None)

    uc = GetCurrentPlanUseCase(plan_repo=repo)
    result = await uc.execute(user_id=uuid.uuid4())
    assert result is None


# ── SwapMealUseCase ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_swap_meal_happy_path() -> None:
    """Generates a replacement meal and persists it."""
    user_id = uuid.uuid4()
    meal_id = uuid.uuid4()
    plan = _make_plan(user_id, meals=[_make_meal(uuid.uuid4(), meal_id)])
    # Fix plan_id in meal
    meal = PlannedMeal(
        id=meal_id,
        plan_id=plan.id,
        day_of_week=0,
        meal_type="lunch",  # type: ignore[arg-type]
        recipe_name="Old",
        recipe_ingredients=[],
        calories=500,
        macros=_make_macros(),
        cook_time_minutes=None,
        difficulty=None,
        servings=1,
        is_logged=False,
        logged_meal_id=None,
    )
    plan = MealPlan(
        id=plan.id,
        user_id=user_id,
        week_start=plan.week_start,
        target_calories=plan.target_calories,
        target_macros=plan.target_macros,
        status="active",
        approximation=False,
        meals=[meal],
    )

    new_meal = PlannedMeal(
        id=uuid.uuid4(),
        plan_id=plan.id,
        day_of_week=0,
        meal_type="lunch",  # type: ignore[arg-type]
        recipe_name="New Swap Recipe",
        recipe_ingredients=["pasta"],
        calories=600,
        macros=_make_macros(),
        cook_time_minutes=25,
        difficulty="medium",
        servings=1,
        is_logged=False,
        logged_meal_id=None,
    )

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=plan)
    repo.update_meal = AsyncMock(return_value=new_meal)

    generator = AsyncMock()
    generator.generate_single_meal = AsyncMock(return_value=new_meal)

    uc = SwapMealUseCase(plan_repo=repo, generator=generator)
    result = await uc.execute(
        user_id=user_id,
        plan_id=plan.id,
        meal_id=meal_id,
    )

    assert result.recipe_name == "New Swap Recipe"
    generator.generate_single_meal.assert_called_once()
    repo.update_meal.assert_called_once()


@pytest.mark.asyncio
async def test_swap_meal_raises_for_non_owner() -> None:
    """Raises PlanNotFoundError when user doesn't own the plan."""
    other_user = uuid.uuid4()
    plan = _make_plan(uuid.uuid4())  # owned by different user

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=plan)

    generator = AsyncMock()
    uc = SwapMealUseCase(plan_repo=repo, generator=generator)

    with pytest.raises(PlanNotFoundError):
        await uc.execute(
            user_id=other_user,
            plan_id=plan.id,
            meal_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_swap_meal_raises_when_plan_not_found() -> None:
    """Raises PlanNotFoundError when plan does not exist."""
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)

    generator = AsyncMock()
    uc = SwapMealUseCase(plan_repo=repo, generator=generator)

    with pytest.raises(PlanNotFoundError):
        await uc.execute(
            user_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            meal_id=uuid.uuid4(),
        )


# ── LogMealUseCase ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_log_meal_happy_path() -> None:
    """Creates a Meal record, marks planned as logged, returns summary."""
    user_id = uuid.uuid4()
    meal_id = uuid.uuid4()
    created_meal_id = uuid.uuid4()

    meal = PlannedMeal(
        id=meal_id,
        plan_id=uuid.uuid4(),
        day_of_week=0,
        meal_type="lunch",  # type: ignore[arg-type]
        recipe_name="Recipe",
        recipe_ingredients=[],
        calories=500,
        macros=_make_macros(),
        cook_time_minutes=None,
        difficulty=None,
        servings=1,
        is_logged=False,
        logged_meal_id=None,
    )
    plan = MealPlan(
        id=meal.plan_id,
        user_id=user_id,
        week_start=date(2026, 4, 14),
        target_calories=2100,
        target_macros=_make_macros(),
        status="active",
        approximation=False,
        meals=[meal],
    )

    # Mock DB session
    db = AsyncMock()
    created_model = MagicMock()
    created_model.id = created_meal_id
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=plan)
    repo.mark_meal_logged = AsyncMock(
        return_value=PlannedMeal(
            id=meal_id,
            plan_id=plan.id,
            day_of_week=0,
            meal_type="lunch",  # type: ignore[arg-type]
            recipe_name="Recipe",
            recipe_ingredients=[],
            calories=500,
            macros=_make_macros(),
            cook_time_minutes=None,
            difficulty=None,
            servings=1,
            is_logged=True,
            logged_meal_id=created_meal_id,
        )
    )

    uc = LogMealUseCase(plan_repo=repo, db=db)

    # Patch the Meal class inside the use case so db.add gets a mock
    from unittest.mock import patch

    with patch("app.meal_plans.application.log_meal_use_case.Meal") as MockMeal:
        mock_instance = MagicMock()
        mock_instance.id = created_meal_id
        MockMeal.return_value = mock_instance

        async def fake_refresh(obj: Any) -> None:
            pass

        db.refresh = fake_refresh

        result = await uc.execute(
            user_id=user_id,
            plan_id=plan.id,
            meal_id=meal_id,
        )

    assert result["planned_meal_id"] == str(meal_id)
    assert result["already_logged"] is False
    repo.mark_meal_logged.assert_called_once()


@pytest.mark.asyncio
async def test_log_meal_already_logged_returns_info() -> None:
    """If meal is already logged, returns info without creating a new Meal."""
    user_id = uuid.uuid4()
    meal_id = uuid.uuid4()
    existing_meal_id = uuid.uuid4()

    meal = PlannedMeal(
        id=meal_id,
        plan_id=uuid.uuid4(),
        day_of_week=0,
        meal_type="lunch",  # type: ignore[arg-type]
        recipe_name="Recipe",
        recipe_ingredients=[],
        calories=500,
        macros=_make_macros(),
        cook_time_minutes=None,
        difficulty=None,
        servings=1,
        is_logged=True,  # already logged
        logged_meal_id=existing_meal_id,
    )
    plan = MealPlan(
        id=meal.plan_id,
        user_id=user_id,
        week_start=date(2026, 4, 14),
        target_calories=2100,
        target_macros=_make_macros(),
        status="active",
        approximation=False,
        meals=[meal],
    )

    db = AsyncMock()
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=plan)

    uc = LogMealUseCase(plan_repo=repo, db=db)
    result = await uc.execute(user_id=user_id, plan_id=plan.id, meal_id=meal_id)

    assert result["already_logged"] is True
    assert result["meal_id"] == str(existing_meal_id)
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_log_meal_raises_for_non_owner() -> None:
    """Raises PlanNotFoundError when user doesn't own the plan."""
    plan = _make_plan(uuid.uuid4())
    other_user = uuid.uuid4()

    db = AsyncMock()
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=plan)

    uc = LogMealUseCase(plan_repo=repo, db=db)
    with pytest.raises(PlanNotFoundError):
        await uc.execute(
            user_id=other_user,
            plan_id=plan.id,
            meal_id=uuid.uuid4(),
        )
