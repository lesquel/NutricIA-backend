"""Unit tests for LLMPlanGenerator — constraint loop and mock validation."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.meal_plans.domain.entities import (
    DietaryConstraints,
    Macros,
    MealPlan,
    PlannedMeal,
)
from app.meal_plans.infrastructure.plan_generator import (
    LLMPlanGenerator,
    _build_plan_prompt,
    _validate_plan_macros,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_macros(p: float = 50.0, c: float = 150.0, f: float = 30.0) -> Macros:
    return Macros(protein_g=p, carbs_g=c, fat_g=f)


def _make_constraints(**kwargs: Any) -> DietaryConstraints:
    defaults = dict(vegetarian=False, vegan=False, gluten_free=False, allergies=[])
    defaults.update(kwargs)
    return DietaryConstraints(**defaults)  # type: ignore[arg-type]


def _make_weekly_json(calories_per_meal: float = 500.0) -> dict:
    """Build a WeeklyPlanSchema-compatible dict with 7 days × 3 meals."""
    days = []
    for day in range(7):
        meals = []
        for mt in ["breakfast", "lunch", "dinner"]:
            meals.append(
                {
                    "meal_type": mt,
                    "recipe_name": f"Recipe {day} {mt}",
                    "recipe_ingredients": ["rice", "chicken"],
                    "calories": calories_per_meal,
                    "protein_g": 30.0,
                    "carbs_g": 60.0,
                    "fat_g": 10.0,
                    "cook_time_minutes": 20,
                    "difficulty": "easy",
                    "servings": 1,
                }
            )
        days.append({"day_of_week": day, "meals": meals})
    return {"days": days}


def _mock_llm_response(json_data: dict) -> MagicMock:
    """Create a mock LLM that returns json_data as a string."""
    import json

    response = MagicMock()
    response.content = json.dumps(json_data)
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=response)
    return llm


# ── Validation helper tests ───────────────────────────────────────────────────


def test_validate_plan_macros_passes_within_tolerance() -> None:
    """Plan with all days within ±10% should return empty issues list."""
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    meals: list[PlannedMeal] = []
    for day in range(7):
        for mt in ["breakfast", "lunch", "dinner"]:
            meals.append(
                PlannedMeal(
                    id=uuid.uuid4(),
                    plan_id=plan_id,
                    day_of_week=day,
                    meal_type=mt,  # type: ignore[arg-type]
                    recipe_name="Test",
                    recipe_ingredients=[],
                    calories=700.0,  # 2100 total per day
                    macros=_make_macros(),
                    cook_time_minutes=None,
                    difficulty=None,
                    servings=1,
                    is_logged=False,
                    logged_meal_id=None,
                )
            )
    plan = MealPlan(
        id=plan_id,
        user_id=user_id,
        week_start=date(2026, 4, 14),
        target_calories=2100,
        target_macros=_make_macros(),
        status="active",
        approximation=False,
        meals=meals,
    )
    issues = _validate_plan_macros(plan, 2100)
    assert issues == []


def test_validate_plan_macros_fails_out_of_tolerance() -> None:
    """A day with 3000 kcal against 2100 target should generate a feedback message."""
    plan_id = uuid.uuid4()
    meals = [
        PlannedMeal(
            id=uuid.uuid4(),
            plan_id=plan_id,
            day_of_week=0,
            meal_type="lunch",  # type: ignore[arg-type]
            recipe_name="Heavy",
            recipe_ingredients=[],
            calories=3000.0,
            macros=_make_macros(),
            cook_time_minutes=None,
            difficulty=None,
            servings=1,
            is_logged=False,
            logged_meal_id=None,
        )
    ]
    plan = MealPlan(
        id=plan_id,
        user_id=uuid.uuid4(),
        week_start=date(2026, 4, 14),
        target_calories=2100,
        target_macros=_make_macros(),
        status="active",
        approximation=False,
        meals=meals,
    )
    issues = _validate_plan_macros(plan, 2100)
    assert len(issues) == 1
    assert "Monday" in issues[0]
    assert "3000" in issues[0]


# ── Prompt builder tests ──────────────────────────────────────────────────────


def test_build_plan_prompt_includes_calories() -> None:
    prompt = _build_plan_prompt(2100, _make_macros(), _make_constraints(), {})
    assert "2100" in prompt
    assert "protein" in prompt.lower()


def test_build_plan_prompt_includes_dietary_constraints() -> None:
    constraints = _make_constraints(
        vegetarian=True, vegan=False, gluten_free=True, allergies=["nuts"]
    )
    prompt = _build_plan_prompt(2100, _make_macros(), constraints, {})
    assert "VEGETARIAN" in prompt
    assert "GLUTEN-FREE" in prompt
    assert "nuts" in prompt


def test_build_plan_prompt_includes_feedback() -> None:
    prompt = _build_plan_prompt(
        2100,
        _make_macros(),
        _make_constraints(),
        {},
        feedback="Day Tuesday was 2500 kcal",
    )
    assert "CORRECTION NEEDED" in prompt
    assert "Tuesday" in prompt


def test_build_plan_prompt_includes_frequent_foods() -> None:
    context = {"frequent_foods": ["arroz", "pollo", "platano"]}
    prompt = _build_plan_prompt(2100, _make_macros(), _make_constraints(), context)
    assert "arroz" in prompt


# ── LLMPlanGenerator tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_generator_returns_plan() -> None:
    """When LLM is None (mock mode), generator returns a deterministic plan."""
    gen = LLMPlanGenerator()
    gen._llm = None  # force mock path

    plan = await gen.generate(
        user_id=uuid.uuid4(),
        target_calories=2100,
        target_macros=_make_macros(),
        constraints=_make_constraints(),
        context={},
        week_start=date(2026, 4, 14),
    )

    assert plan.approximation is False
    assert len(plan.meals) == 28  # 7 days × 4 meals
    assert plan.target_calories == 2100


@pytest.mark.asyncio
async def test_successful_generation_no_retries() -> None:
    """LLM returns valid plan on first attempt → approximation=False."""
    gen = LLMPlanGenerator()
    # Plan with 700 cal/meal × 3 meals = 2100/day — exactly on target
    weekly_json = _make_weekly_json(calories_per_meal=700.0)
    gen._llm = _mock_llm_response(weekly_json)

    plan = await gen.generate(
        user_id=uuid.uuid4(),
        target_calories=2100,
        target_macros=_make_macros(),
        constraints=_make_constraints(),
        context={},
        week_start=date(2026, 4, 14),
    )

    assert plan.approximation is False
    # LLM called exactly once
    gen._llm.ainvoke.assert_called_once()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_one_retry_needed_then_passes() -> None:
    """First LLM call returns bad plan, second returns valid plan → approximation=False."""
    import json

    gen = LLMPlanGenerator()

    # Bad plan (3000 cal/meal × 3 = 9000/day — way over)
    bad_json = _make_weekly_json(calories_per_meal=3000.0)
    # Good plan (700 cal/meal × 3 = 2100/day — on target)
    good_json = _make_weekly_json(calories_per_meal=700.0)

    bad_response = MagicMock()
    bad_response.content = json.dumps(bad_json)
    good_response = MagicMock()
    good_response.content = json.dumps(good_json)

    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=[bad_response, good_response])
    gen._llm = llm

    plan = await gen.generate(
        user_id=uuid.uuid4(),
        target_calories=2100,
        target_macros=_make_macros(),
        constraints=_make_constraints(),
        context={},
        week_start=date(2026, 4, 14),
    )

    assert plan.approximation is False
    assert llm.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_two_retries_exhausted_returns_approximation_true() -> None:
    """After MAX_RETRIES (2), returns plan with approximation=True."""
    import json

    gen = LLMPlanGenerator()
    # Always returns a bad plan (9000/day > 10% of 2100)
    bad_json = _make_weekly_json(calories_per_meal=3000.0)

    llm = AsyncMock()
    bad_response = MagicMock()
    bad_response.content = json.dumps(bad_json)
    llm.ainvoke = AsyncMock(return_value=bad_response)
    gen._llm = llm

    plan = await gen.generate(
        user_id=uuid.uuid4(),
        target_calories=2100,
        target_macros=_make_macros(),
        constraints=_make_constraints(),
        context={},
        week_start=date(2026, 4, 14),
    )

    assert plan.approximation is True
    # Called MAX_RETRIES + 1 = 3 times total
    assert llm.ainvoke.call_count == gen.MAX_RETRIES + 1


@pytest.mark.asyncio
async def test_second_retry_passes_not_approximation() -> None:
    """Two bad attempts then one good → approximation=False."""
    import json

    gen = LLMPlanGenerator()
    bad_json = _make_weekly_json(calories_per_meal=3000.0)
    good_json = _make_weekly_json(calories_per_meal=700.0)

    bad_response = MagicMock()
    bad_response.content = json.dumps(bad_json)
    good_response = MagicMock()
    good_response.content = json.dumps(good_json)

    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=[bad_response, bad_response, good_response])
    gen._llm = llm

    plan = await gen.generate(
        user_id=uuid.uuid4(),
        target_calories=2100,
        target_macros=_make_macros(),
        constraints=_make_constraints(),
        context={},
        week_start=date(2026, 4, 14),
    )

    assert plan.approximation is False
    assert llm.ainvoke.call_count == 3
