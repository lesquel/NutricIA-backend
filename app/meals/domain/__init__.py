"""Meals domain — value objects and exceptions."""

from enum import StrEnum


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    SNACK = "snack"
    DINNER = "dinner"


class FoodAnalysisError(Exception):
    """Raised when the AI detects a non-food or blurry image."""

    def __init__(self, error_type: str):
        self.error_type = error_type
        super().__init__(f"Food analysis failed: {error_type}")
