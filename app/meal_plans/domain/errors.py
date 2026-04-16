"""Meal plans domain errors."""

from __future__ import annotations


class MealPlanError(Exception):
    """Base error for the meal_plans domain."""


class PlanValidationError(MealPlanError):
    """Raised when a meal plan fails validation."""


class PlanNotFoundError(MealPlanError):
    """Raised when a meal plan cannot be found."""


class MacroTargetUnreachableError(MealPlanError):
    """Raised when the generator cannot satisfy macro targets within tolerance."""
