"""Unit tests for meal_plans domain entities."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.meal_plans.domain.entities import (
    DietaryConstraints,
    Macros,
    MealPlan,
    PlannedMeal,
)


# ── Macros ───────────────────────────────────────────────────


def test_macros_rejects_negative_protein() -> None:
    with pytest.raises(ValueError, match="protein_g"):
        Macros(protein_g=-1.0, carbs_g=100.0, fat_g=50.0)


def test_macros_rejects_negative_carbs() -> None:
    with pytest.raises(ValueError, match="carbs_g"):
        Macros(protein_g=100.0, carbs_g=-0.1, fat_g=50.0)


def test_macros_rejects_negative_fat() -> None:
    with pytest.raises(ValueError, match="fat_g"):
        Macros(protein_g=100.0, carbs_g=100.0, fat_g=-5.0)


def test_macros_zero_values_are_valid() -> None:
    m = Macros(protein_g=0.0, carbs_g=0.0, fat_g=0.0)
    assert m.protein_g == 0.0


def test_macros_valid_construction() -> None:
    m = Macros(protein_g=50.0, carbs_g=200.0, fat_g=70.0)
    assert m.carbs_g == 200.0


# ── PlannedMeal ──────────────────────────────────────────────


def _valid_planned_meal(**overrides: object) -> PlannedMeal:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "plan_id": uuid.uuid4(),
        "day_of_week": 0,
        "meal_type": "breakfast",
        "recipe_name": "Avena con frutas",
        "recipe_ingredients": ["avena", "banana", "leche"],
        "calories": 350.0,
        "macros": Macros(protein_g=12.0, carbs_g=55.0, fat_g=8.0),
        "cook_time_minutes": 10,
        "difficulty": "easy",
        "servings": 1,
        "is_logged": False,
        "logged_meal_id": None,
    }
    defaults.update(overrides)
    return PlannedMeal(**defaults)  # type: ignore[arg-type]


def test_planned_meal_valid() -> None:
    meal = _valid_planned_meal()
    assert meal.recipe_name == "Avena con frutas"


def test_planned_meal_rejects_calories_zero() -> None:
    with pytest.raises(ValueError, match="calories"):
        _valid_planned_meal(calories=0.0)


def test_planned_meal_rejects_calories_negative() -> None:
    with pytest.raises(ValueError, match="calories"):
        _valid_planned_meal(calories=-100.0)


def test_planned_meal_rejects_servings_less_than_one() -> None:
    with pytest.raises(ValueError, match="servings"):
        _valid_planned_meal(servings=0)


def test_planned_meal_rejects_day_of_week_negative() -> None:
    with pytest.raises(ValueError, match="day_of_week"):
        _valid_planned_meal(day_of_week=-1)


def test_planned_meal_rejects_day_of_week_seven() -> None:
    with pytest.raises(ValueError, match="day_of_week"):
        _valid_planned_meal(day_of_week=7)


def test_planned_meal_day_of_week_six_is_valid() -> None:
    meal = _valid_planned_meal(day_of_week=6)
    assert meal.day_of_week == 6


# ── MealPlan ─────────────────────────────────────────────────


def _make_meal(
    day: int, meal_type: str = "breakfast", calories: float = 400.0
) -> PlannedMeal:
    return PlannedMeal(
        id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        day_of_week=day,
        meal_type=meal_type,  # type: ignore[arg-type]
        recipe_name="Test Meal",
        recipe_ingredients=["ingredient"],
        calories=calories,
        macros=Macros(protein_g=20.0, carbs_g=40.0, fat_g=10.0),
        cook_time_minutes=15,
        difficulty="easy",
        servings=1,
        is_logged=False,
        logged_meal_id=None,
    )


def _valid_meal_plan(meals: list[PlannedMeal] | None = None) -> MealPlan:
    if meals is None:
        meals = []
    return MealPlan(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        week_start=date(2026, 4, 13),
        target_calories=2000,
        target_macros=Macros(protein_g=150.0, carbs_g=200.0, fat_g=70.0),
        status="active",
        approximation=False,
        meals=meals,
    )


def test_meal_plan_meals_for_day_filters_correctly() -> None:
    monday_breakfast = _make_meal(day=0, meal_type="breakfast")
    monday_lunch = _make_meal(day=0, meal_type="lunch")
    tuesday_breakfast = _make_meal(day=1, meal_type="breakfast")

    plan = _valid_meal_plan(meals=[monday_breakfast, monday_lunch, tuesday_breakfast])

    monday_meals = plan.meals_for_day(0)
    assert len(monday_meals) == 2
    assert monday_breakfast in monday_meals
    assert monday_lunch in monday_meals
    assert tuesday_breakfast not in monday_meals


def test_meal_plan_meals_for_day_empty_day() -> None:
    plan = _valid_meal_plan(meals=[_make_meal(day=0)])
    assert plan.meals_for_day(3) == []


def test_meal_plan_daily_calories_sums_correctly() -> None:
    plan = _valid_meal_plan(
        meals=[
            _make_meal(day=2, calories=400.0),
            _make_meal(day=2, calories=600.0),
            _make_meal(day=3, calories=300.0),
        ]
    )
    assert plan.daily_calories(2) == pytest.approx(1000.0)
    assert plan.daily_calories(3) == pytest.approx(300.0)


def test_meal_plan_daily_calories_empty_day_is_zero() -> None:
    plan = _valid_meal_plan()
    assert plan.daily_calories(0) == 0.0


def test_meal_plan_daily_macros_sums_correctly() -> None:
    meal_a = PlannedMeal(
        id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        day_of_week=1,
        meal_type="breakfast",
        recipe_name="A",
        recipe_ingredients=["x"],
        calories=300.0,
        macros=Macros(protein_g=30.0, carbs_g=40.0, fat_g=10.0),
        cook_time_minutes=5,
        difficulty="easy",
        servings=1,
        is_logged=False,
        logged_meal_id=None,
    )
    meal_b = PlannedMeal(
        id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        day_of_week=1,
        meal_type="lunch",
        recipe_name="B",
        recipe_ingredients=["y"],
        calories=500.0,
        macros=Macros(protein_g=50.0, carbs_g=60.0, fat_g=20.0),
        cook_time_minutes=20,
        difficulty="medium",
        servings=1,
        is_logged=False,
        logged_meal_id=None,
    )
    plan = _valid_meal_plan(meals=[meal_a, meal_b])
    daily = plan.daily_macros(1)
    assert daily.protein_g == pytest.approx(80.0)
    assert daily.carbs_g == pytest.approx(100.0)
    assert daily.fat_g == pytest.approx(30.0)


def test_meal_plan_daily_macros_empty_day_is_zeros() -> None:
    plan = _valid_meal_plan()
    daily = plan.daily_macros(0)
    assert daily.protein_g == 0.0
    assert daily.carbs_g == 0.0
    assert daily.fat_g == 0.0


def test_meal_plan_rejects_more_than_28_meals() -> None:
    meals = [_make_meal(day=i % 7) for i in range(29)]
    with pytest.raises(ValueError):
        _valid_meal_plan(meals=meals)


# ── DietaryConstraints ───────────────────────────────────────


def test_dietary_constraints_valid() -> None:
    dc = DietaryConstraints(
        vegetarian=True,
        vegan=False,
        gluten_free=True,
        allergies=["maní", "mariscos"],
    )
    assert dc.vegetarian is True
    assert "maní" in dc.allergies


def test_dietary_constraints_no_allergies() -> None:
    dc = DietaryConstraints(
        vegetarian=False, vegan=False, gluten_free=False, allergies=[]
    )
    assert dc.allergies == []
