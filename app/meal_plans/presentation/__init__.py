"""Meal plans presentation — Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Shared sub-schemas ────────────────────────────────────────────────────────


class MacrosSchema(BaseModel):
    """Macro nutrients schema (request + response)."""

    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class DietaryConstraintsSchema(BaseModel):
    """Dietary constraints for plan generation."""

    vegetarian: bool = False
    vegan: bool = False
    gluten_free: bool = False
    allergies: list[str] = Field(default_factory=list)


# ── Request schemas ───────────────────────────────────────────────────────────


class GeneratePlanRequest(BaseModel):
    """Body for POST /plans/generate."""

    target_calories: int = Field(gt=0, description="Daily calorie target")
    target_macros: MacrosSchema
    constraints: DietaryConstraintsSchema = Field(
        default_factory=DietaryConstraintsSchema
    )
    week_start: date | None = Field(
        default=None,
        description="ISO date of Monday for the plan week (defaults to current week's Monday)",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="User context: frequent_foods, etc.",
    )


class SwapMealRequest(BaseModel):
    """Body for PATCH /plans/{plan_id}/meals/{meal_id}."""

    constraints: DietaryConstraintsSchema | None = None
    context: dict[str, Any] = Field(default_factory=dict)


# ── Response schemas ──────────────────────────────────────────────────────────


class PlannedMealResponse(BaseModel):
    """Response schema for a single planned meal."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    plan_id: uuid.UUID
    day_of_week: int
    meal_type: str
    recipe_name: str
    recipe_ingredients: list[str]
    calories: float
    macros: MacrosSchema
    cook_time_minutes: int | None
    difficulty: str | None
    servings: int
    is_logged: bool
    logged_meal_id: uuid.UUID | None


class MealPlanResponse(BaseModel):
    """Response schema for a full meal plan."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    week_start: date
    target_calories: int
    target_macros: MacrosSchema
    status: Literal["active", "archived", "completed"]
    approximation: bool
    meals: list[PlannedMealResponse]


class LogMealResponse(BaseModel):
    """Response for POST /plans/{plan_id}/meals/{meal_id}/log."""

    meal_id: str
    planned_meal_id: str
    already_logged: bool
