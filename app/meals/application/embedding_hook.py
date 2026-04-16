"""Meals application — post-save embedding hook.

Generates a vector embedding for a saved meal and upserts it into the
meal_embeddings vector store.  This is a fire-and-forget operation:
failures are logged but never re-raised.

TODO: add retry strategy (e.g. exponential backoff via tenacity) for
transient embedding provider failures — out of scope for v1.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.meals.infrastructure import Meal
    from app.shared.domain.ports import VectorStorePort
    from app.shared.infrastructure.embeddings import EmbeddingsProviderPort

logger = logging.getLogger("nutricia.meals.embedding")


def _build_content_text(meal: "Meal") -> str:
    """Build a human-readable text representation of the meal for embedding."""
    tag_labels = ", ".join(tag.label for tag in meal.tags) if meal.tags else "none"
    return (
        f"{meal.name}, "
        f"{meal.calories:.0f} kcal, "
        f"{meal.protein_g:.1f}g protein, "
        f"{meal.carbs_g:.1f}g carbs, "
        f"{meal.fat_g:.1f}g fat, "
        f"tags: {tag_labels}"
    )


async def generate_meal_embedding(
    meal: "Meal",
    vector_store: "VectorStorePort",
    embeddings_provider: "EmbeddingsProviderPort",
) -> None:
    """Generate and upsert the embedding for a meal.

    This function is designed to be called as a background task.  Any
    exception is caught, logged, and swallowed — the meal save response
    must not be blocked or failed by embedding errors.

    Parameters
    ----------
    meal:
        The saved Meal ORM model (must have id, name, calories, protein_g,
        carbs_g, fat_g, tags attributes).
    vector_store:
        VectorStorePort adapter targeting the meal_embeddings table.
    embeddings_provider:
        EmbeddingsProviderPort for generating the vector.
    """
    try:
        content_text = _build_content_text(meal)
        embedding = await embeddings_provider.embed(content_text)
        await vector_store.upsert(
            id=meal.id,
            embedding=embedding,
            metadata={
                "meal_id": str(meal.id),
                "content_text": content_text,
            },
        )
        logger.debug("Meal embedding upserted for meal_id=%s", meal.id)
    except Exception as exc:
        logger.error(
            "Failed to generate/upsert embedding for meal_id=%s: %s",
            getattr(meal, "id", "unknown"),
            exc,
        )
