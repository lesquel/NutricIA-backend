"""Meal plans domain entities — no framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Literal

MealType = Literal["breakfast", "lunch", "snack", "dinner"]
Difficulty = Literal["easy", "medium", "hard"]


@dataclass
class Macros:
    protein_g: float
    carbs_g: float
    fat_g: float

    def __post_init__(self) -> None:
        if self.protein_g < 0:
            raise ValueError("protein_g must be >= 0")
        if self.carbs_g < 0:
            raise ValueError("carbs_g must be >= 0")
        if self.fat_g < 0:
            raise ValueError("fat_g must be >= 0")


@dataclass
class PlannedMeal:
    id: uuid.UUID
    plan_id: uuid.UUID
    day_of_week: int  # 0=Monday .. 6=Sunday
    meal_type: MealType
    recipe_name: str
    recipe_ingredients: list[str]
    calories: float
    macros: Macros
    cook_time_minutes: int | None
    difficulty: Difficulty | None
    servings: int
    is_logged: bool
    logged_meal_id: uuid.UUID | None

    def __post_init__(self) -> None:
        if self.calories <= 0:
            raise ValueError("calories must be > 0")
        if self.servings < 1:
            raise ValueError("servings must be >= 1")
        if not (0 <= self.day_of_week <= 6):
            raise ValueError("day_of_week must be in 0..6")


@dataclass
class MealPlan:
    id: uuid.UUID
    user_id: uuid.UUID
    week_start: date
    target_calories: int
    target_macros: Macros
    status: Literal["active", "archived", "completed"]
    approximation: bool
    meals: list[PlannedMeal]

    def __post_init__(self) -> None:
        if len(self.meals) > 28:
            raise ValueError(
                f"A meal plan can have at most 28 meals (3-4 per day × 7 days), "
                f"got {len(self.meals)}"
            )

    def meals_for_day(self, day_of_week: int) -> list[PlannedMeal]:
        """Return all meals scheduled for the given day (0=Monday .. 6=Sunday)."""
        return [m for m in self.meals if m.day_of_week == day_of_week]

    def daily_calories(self, day_of_week: int) -> float:
        """Sum calories for all meals on the given day."""
        return sum(m.calories for m in self.meals_for_day(day_of_week))

    def daily_macros(self, day_of_week: int) -> Macros:
        """Sum macros for all meals on the given day."""
        meals = self.meals_for_day(day_of_week)
        return Macros(
            protein_g=sum(m.macros.protein_g for m in meals),
            carbs_g=sum(m.macros.carbs_g for m in meals),
            fat_g=sum(m.macros.fat_g for m in meals),
        )

    def validate_complete(self) -> None:
        """Raise PlanValidationError if the plan has no meals."""
        from app.meal_plans.domain.errors import PlanValidationError

        if len(self.meals) == 0:
            raise PlanValidationError(
                "A complete meal plan must have at least one meal."
            )


@dataclass
class DietaryConstraints:
    vegetarian: bool
    vegan: bool
    gluten_free: bool
    allergies: list[str]
