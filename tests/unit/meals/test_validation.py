"""Tests for meal schema validation (MealCreate.meal_type enum)."""

import pytest
from pydantic import ValidationError

from app.meals.presentation import MealCreate


VALID_MEAL_BASE = dict(
    name="Salad",
    calories=200,
    protein_g=10,
    carbs_g=20,
    fat_g=5,
)


class TestMealCreateMealType:
    """MealCreate.meal_type must be a MealType enum value."""

    def test_breakfast_is_valid(self) -> None:
        meal = MealCreate(**VALID_MEAL_BASE, meal_type="breakfast")
        assert meal.meal_type == "breakfast"

    def test_lunch_is_valid(self) -> None:
        meal = MealCreate(**VALID_MEAL_BASE, meal_type="lunch")
        assert meal.meal_type == "lunch"

    def test_dinner_is_valid(self) -> None:
        meal = MealCreate(**VALID_MEAL_BASE, meal_type="dinner")
        assert meal.meal_type == "dinner"

    def test_snack_is_valid(self) -> None:
        meal = MealCreate(**VALID_MEAL_BASE, meal_type="snack")
        assert meal.meal_type == "snack"

    def test_brunch_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MealCreate(**VALID_MEAL_BASE, meal_type="brunch")

    def test_default_is_snack(self) -> None:
        meal = MealCreate(**VALID_MEAL_BASE)
        assert meal.meal_type == "snack"
