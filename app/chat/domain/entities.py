"""Chat domain entities — no framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

MessageRole = Literal["user", "assistant", "system", "tool"]


@dataclass
class Conversation:
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class Message:
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    metadata: dict[str, Any]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("content must not be empty")


@dataclass
class RecipeSuggestion:
    name: str
    ingredients: list[str]
    macros_per_serving: dict[str, Any]  # {calories, protein_g, carbs_g, fat_g}
    cook_time_minutes: int
    difficulty: Literal["easy", "medium", "hard"]
    servings: int
    steps: list[str]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.ingredients:
            raise ValueError("ingredients must not be empty")
        if self.servings < 1:
            raise ValueError("servings must be >= 1")
        if self.cook_time_minutes < 0:
            raise ValueError("cook_time_minutes must be >= 0")


@dataclass
class ConversationContext:
    """Input context passed to the LLM for a chat turn."""

    user_id: uuid.UUID
    recent_meals: list[dict[str, Any]]
    retrieved_recipes: list[dict[str, Any]]
    user_food_profile: dict[str, Any] | None
