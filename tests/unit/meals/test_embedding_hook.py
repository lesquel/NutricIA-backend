"""Unit tests for meal embedding hook."""

from __future__ import annotations

import logging
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.meals.application.embedding_hook import generate_meal_embedding


def _make_meal(
    name: str = "Pollo a la plancha",
    calories: float = 250.0,
    protein_g: float = 35.0,
    carbs_g: float = 5.0,
    fat_g: float = 10.0,
    tags: list[str] | None = None,
) -> object:
    """Return a minimal Meal-like object (duck-typed)."""

    class FakeMeal:
        id = uuid.uuid4()

    meal = FakeMeal()
    meal.id = uuid.uuid4()  # type: ignore[attr-defined]
    meal.name = name  # type: ignore[attr-defined]
    meal.calories = calories  # type: ignore[attr-defined]
    meal.protein_g = protein_g  # type: ignore[attr-defined]
    meal.carbs_g = carbs_g  # type: ignore[attr-defined]
    meal.fat_g = fat_g  # type: ignore[attr-defined]
    meal.tags = [type("Tag", (), {"label": t})() for t in (tags or [])]  # type: ignore[attr-defined]
    return meal


@pytest.mark.asyncio
async def test_content_text_format() -> None:
    """Verify content_text passed to embeddings has correct format."""
    meal = _make_meal(
        name="Arroz con pollo",
        calories=450,
        protein_g=30,
        carbs_g=55,
        fat_g=8,
        tags=["Protein", "Comfort Food"],
    )
    vector_store = AsyncMock()
    embeddings_provider = AsyncMock()
    embeddings_provider.embed.return_value = [0.1] * 1536

    await generate_meal_embedding(meal, vector_store, embeddings_provider)  # type: ignore[arg-type]

    call_args = embeddings_provider.embed.call_args[0][0]
    assert "Arroz con pollo" in call_args
    assert "450" in call_args
    assert "30" in call_args
    assert "55" in call_args
    assert "8" in call_args
    assert "Protein" in call_args
    assert "Comfort Food" in call_args


@pytest.mark.asyncio
async def test_upsert_called_with_correct_args() -> None:
    """Verify vector_store.upsert is called with meal.id and embedding."""
    meal = _make_meal()
    vector_store = AsyncMock()
    embeddings_provider = AsyncMock()
    expected_embedding = [0.5] * 1536
    embeddings_provider.embed.return_value = expected_embedding

    await generate_meal_embedding(meal, vector_store, embeddings_provider)  # type: ignore[arg-type]

    vector_store.upsert.assert_called_once()
    call_kwargs = vector_store.upsert.call_args
    # id should be meal.id
    assert call_kwargs[1]["id"] == meal.id or call_kwargs[0][0] == meal.id  # type: ignore[attr-defined]
    # embedding should match
    called_embedding = (
        call_kwargs[1].get("embedding") or call_kwargs[0][1]
        if len(call_kwargs[0]) > 1
        else call_kwargs[1].get("embedding")
    )
    assert called_embedding == expected_embedding


@pytest.mark.asyncio
async def test_upsert_metadata_contains_meal_id() -> None:
    """Verify metadata passed to upsert includes meal_id."""
    meal = _make_meal()
    vector_store = AsyncMock()
    embeddings_provider = AsyncMock()
    embeddings_provider.embed.return_value = [0.1] * 1536

    await generate_meal_embedding(meal, vector_store, embeddings_provider)  # type: ignore[arg-type]

    vector_store.upsert.assert_called_once()
    # Extract metadata from call
    call = vector_store.upsert.call_args
    metadata = call[1].get("metadata") or (call[0][2] if len(call[0]) > 2 else None)
    assert metadata is not None
    assert str(meal.id) in str(metadata.get("meal_id", ""))  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_failure_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    """If embeddings_provider raises, exception is caught and logged, not re-raised."""
    meal = _make_meal()
    vector_store = AsyncMock()
    embeddings_provider = AsyncMock()
    embeddings_provider.embed.side_effect = RuntimeError("quota exceeded")

    with caplog.at_level(logging.ERROR):
        # Must NOT raise
        await generate_meal_embedding(meal, vector_store, embeddings_provider)  # type: ignore[arg-type]

    # upsert should NOT have been called
    vector_store.upsert.assert_not_called()
    # Error should have been logged
    assert (
        any("quota exceeded" in r.message for r in caplog.records)
        or len(caplog.records) > 0
    )


@pytest.mark.asyncio
async def test_upsert_failure_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    """If vector_store.upsert raises, exception is caught and logged."""
    meal = _make_meal()
    vector_store = AsyncMock()
    vector_store.upsert.side_effect = RuntimeError("connection failed")
    embeddings_provider = AsyncMock()
    embeddings_provider.embed.return_value = [0.1] * 1536

    with caplog.at_level(logging.ERROR):
        # Must NOT raise
        await generate_meal_embedding(meal, vector_store, embeddings_provider)  # type: ignore[arg-type]

    assert len(caplog.records) > 0
