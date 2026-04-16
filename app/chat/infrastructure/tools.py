"""Chat infrastructure — Pydantic tool schemas for LLM tool-calling.

These models are used with model.bind_tools() so that LangChain emits
structured tool_calls in the message stream rather than requiring internal
tool execution.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RecipeSuggestionTool(BaseModel):
    """Suggest a structured recipe to the user."""

    name: str = Field(description="Recipe name")
    ingredients: list[str] = Field(description="List of ingredients")
    macros_per_serving: dict[str, float] = Field(
        description="Macros per serving: calories, protein_g, carbs_g, fat_g"
    )
    cook_time_minutes: int = Field(ge=0, description="Cooking time in minutes")
    difficulty: Literal["easy", "medium", "hard"] = Field(
        description="Recipe difficulty"
    )
    servings: int = Field(ge=1, description="Number of servings")
    steps: list[str] = Field(description="Ordered preparation steps")


class SwapPlannedMealTool(BaseModel):
    """Swap a planned meal in the user's current weekly plan."""

    plan_id: str = Field(description="The UUID of the meal plan")
    day_of_week: int = Field(ge=0, le=6, description="0=Monday, 6=Sunday")
    meal_type: Literal["breakfast", "lunch", "snack", "dinner"] = Field(
        description="Type of meal to swap"
    )
    constraints_text: str = Field(
        description="Free-text constraints, e.g. 'vegetarian', 'low-carb'"
    )
