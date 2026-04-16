"""Chat infrastructure — Composite RAG retriever.

Combines multiple retrieval strategies to build a ConversationContext:
  1. Semantic search in meal_embeddings (user's past meals similar to query)
  2. Semantic search in food_catalog (relevant foods from the catalog)
  3. User food profile (preferences / avoided tags)
  4. Chronological last-5 meals (what the user actually ate recently)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import desc, select

from app.chat.domain.entities import ConversationContext
from app.meals.infrastructure import Meal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.domain.ports import VectorStorePort
    from app.shared.infrastructure.embeddings import EmbeddingsProviderPort

logger = logging.getLogger("nutricia.chat.rag")

_MEAL_SEMANTIC_K = 3
_CATALOG_K = 5
_RECENT_MEALS_LIMIT = 5


class CompositeRAGRetriever:
    """Retrieves conversation context from multiple data sources.

    Parameters
    ----------
    meal_vector_store:
        VectorStorePort targeting the meal_embeddings table.
    catalog_vector_store:
        VectorStorePort targeting the food_catalog table.
    user_food_profile_repo:
        Repository for UserFoodProfile (any object with get_for_user(user_id) async).
    embeddings_provider:
        EmbeddingsProviderPort for embedding the query.
    db_session:
        Active AsyncSession for the relational DB queries.
    """

    def __init__(
        self,
        meal_vector_store: "VectorStorePort",
        catalog_vector_store: "VectorStorePort",
        user_food_profile_repo: Any,
        embeddings_provider: "EmbeddingsProviderPort | None",
        db_session: "AsyncSession",
    ) -> None:
        self._meal_vs = meal_vector_store
        self._catalog_vs = catalog_vector_store
        self._profile_repo = user_food_profile_repo
        self._embeddings: Any = embeddings_provider
        self._session = db_session

    async def retrieve_context(
        self,
        user_id: uuid.UUID,
        query: str,
    ) -> ConversationContext:
        """Build a ConversationContext from all retrieval sources.

        All sources are queried independently.  If any individual source
        fails, it is skipped and logged (graceful degradation).
        """
        # Step 1: Embed the query
        query_embedding: list[float] = []
        if self._embeddings is not None:
            try:
                query_embedding = await self._embeddings.embed(query)
            except Exception as exc:
                logger.warning("Failed to embed RAG query: %s", exc)

        # Step 2: Semantic search in user's meal embeddings
        semantic_meals: list[dict[str, Any]] = []
        if query_embedding:
            try:
                results = await self._meal_vs.similarity_search(
                    embedding=query_embedding,
                    k=_MEAL_SEMANTIC_K,
                    filter={"user_id": str(user_id)},
                )
                semantic_meals = [
                    {"meal_id": str(r.id), "score": r.score, **r.metadata}
                    for r in results
                ]
            except Exception as exc:
                logger.warning("Meal semantic search failed: %s", exc)

        # Step 3: Semantic search in food catalog
        retrieved_recipes: list[dict[str, Any]] = []
        if query_embedding:
            try:
                catalog_results = await self._catalog_vs.similarity_search(
                    embedding=query_embedding,
                    k=_CATALOG_K,
                )
                retrieved_recipes = [
                    {"entry_id": str(r.id), "score": r.score, **r.metadata}
                    for r in catalog_results
                ]
            except Exception as exc:
                logger.warning("Catalog semantic search failed: %s", exc)

        # Step 4: User food profile
        user_food_profile: dict[str, Any] | None = None
        try:
            profile = await self._profile_repo.get_for_user(user_id)
            if profile is not None:
                user_food_profile = (
                    profile if isinstance(profile, dict) else vars(profile)
                )
        except Exception as exc:
            logger.warning("Failed to fetch user food profile: %s", exc)

        # Step 5: Chronological last-N meals from DB
        recent_meals: list[dict[str, Any]] = []
        try:
            stmt = (
                select(Meal)
                .where(Meal.user_id == user_id)
                .order_by(desc(Meal.logged_at))
                .limit(_RECENT_MEALS_LIMIT)
            )
            result = await self._session.execute(stmt)
            db_meals = result.scalars().all()
            recent_meals = [
                {
                    "id": str(m.id),
                    "name": m.name,
                    "calories": m.calories,
                    "protein_g": m.protein_g,
                    "carbs_g": m.carbs_g,
                    "fat_g": m.fat_g,
                    "logged_at": m.logged_at.isoformat() if m.logged_at else None,
                }
                for m in db_meals
            ]
        except Exception as exc:
            logger.warning("Failed to fetch recent meals: %s", exc)

        # Merge semantic + chronological meals (deduplicate by meal_id)
        all_recent = {**{m.get("meal_id", ""): m for m in semantic_meals}}
        for m in recent_meals:
            if m["id"] not in all_recent:
                all_recent[m["id"]] = m
        merged_meals = list(all_recent.values())[
            : _RECENT_MEALS_LIMIT + _MEAL_SEMANTIC_K
        ]

        return ConversationContext(
            user_id=user_id,
            recent_meals=merged_meals,
            retrieved_recipes=retrieved_recipes,
            user_food_profile=user_food_profile,
        )
