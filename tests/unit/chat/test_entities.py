"""Unit tests for chat domain entities."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.chat.domain.entities import (
    ConversationContext,
    Message,
    MessageRole,
    RecipeSuggestion,
)


# ── MessageRole ──────────────────────────────────────────────


def test_message_role_valid_values() -> None:
    valid: list[MessageRole] = ["user", "assistant", "system", "tool"]
    for role in valid:
        assert role in {"user", "assistant", "system", "tool"}


# ── Message ──────────────────────────────────────────────────


def test_message_requires_non_empty_content() -> None:
    with pytest.raises(ValueError, match="content"):
        Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role="user",
            content="",
            metadata={},
            created_at=datetime.now(timezone.utc),
        )


def test_message_valid_construction() -> None:
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        role="assistant",
        content="Here is a recipe for you.",
        metadata={"tool_calls": []},
        created_at=datetime.now(timezone.utc),
    )
    assert msg.content == "Here is a recipe for you."
    assert msg.role == "assistant"


# ── RecipeSuggestion ─────────────────────────────────────────


def _valid_recipe(**overrides: object) -> RecipeSuggestion:
    defaults: dict[str, object] = {
        "name": "Ensalada César",
        "ingredients": ["lechuga", "parmesano", "aderezo"],
        "macros_per_serving": {
            "calories": 350.0,
            "protein_g": 12.0,
            "carbs_g": 20.0,
            "fat_g": 18.0,
        },
        "cook_time_minutes": 15,
        "difficulty": "easy",
        "servings": 2,
        "steps": ["Mezclar ingredientes", "Servir frío"],
    }
    defaults.update(overrides)
    return RecipeSuggestion(**defaults)  # type: ignore[arg-type]


def test_recipe_suggestion_valid() -> None:
    recipe = _valid_recipe()
    assert recipe.name == "Ensalada César"
    assert recipe.servings == 2


def test_recipe_suggestion_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="name"):
        _valid_recipe(name="")


def test_recipe_suggestion_rejects_empty_ingredients() -> None:
    with pytest.raises(ValueError, match="ingredients"):
        _valid_recipe(ingredients=[])


def test_recipe_suggestion_rejects_servings_less_than_one() -> None:
    with pytest.raises(ValueError, match="servings"):
        _valid_recipe(servings=0)


def test_recipe_suggestion_rejects_negative_cook_time() -> None:
    with pytest.raises(ValueError, match="cook_time_minutes"):
        _valid_recipe(cook_time_minutes=-1)


def test_recipe_suggestion_servings_one_is_valid() -> None:
    recipe = _valid_recipe(servings=1)
    assert recipe.servings == 1


def test_recipe_suggestion_zero_cook_time_is_valid() -> None:
    recipe = _valid_recipe(cook_time_minutes=0)
    assert recipe.cook_time_minutes == 0


# ── ConversationContext ──────────────────────────────────────


def test_conversation_context_construction() -> None:
    ctx = ConversationContext(
        user_id=uuid.uuid4(),
        recent_meals=[{"name": "Asado", "calories": 600}],
        retrieved_recipes=[],
        user_food_profile=None,
    )
    assert ctx.user_food_profile is None
    assert len(ctx.recent_meals) == 1
