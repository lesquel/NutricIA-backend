"""Catalog infrastructure — FoodCatalogRepositoryImpl."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.domain.entities import FoodCatalogEntry
from app.catalog.infrastructure.models import FoodCatalogModel
from app.shared.domain.ports import VectorStorePort, SearchResult


class FoodCatalogRepositoryImpl:
    """Concrete repository backed by SQLAlchemy + an injected VectorStorePort.

    Parameters
    ----------
    session:
        An open AsyncSession (injected per request/test).
    vector_store:
        Any adapter that implements VectorStorePort (InMemory for tests,
        PgVectorAdapter for production).
    """

    def __init__(
        self,
        session: AsyncSession,
        vector_store: VectorStorePort,
    ) -> None:
        self._session = session
        self._vector_store = vector_store

    # ── helpers ───────────────────────────────────────────────────────────────

    def _model_to_entity(self, model: FoodCatalogModel) -> FoodCatalogEntry:
        aliases: list[str] = json.loads(model.aliases) if model.aliases else []
        macros: dict[str, Any] = (
            json.loads(model.macros_per_100g) if model.macros_per_100g else {}
        )
        return FoodCatalogEntry(
            id=model.id,
            canonical_name=model.canonical_name,
            aliases=aliases,
            macros_per_100g=macros,
            source=model.source,
            created_at=model.created_at,
        )

    # ── port implementation ────────────────────────────────────────────────────

    async def upsert(
        self,
        entry: FoodCatalogEntry,
        embedding: list[float],
    ) -> FoodCatalogEntry:
        """Insert or update a catalog entry and persist its embedding vector."""
        stmt = select(FoodCatalogModel).where(
            FoodCatalogModel.canonical_name == entry.canonical_name,
            FoodCatalogModel.source == entry.source,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            model = FoodCatalogModel(
                id=entry.id,
                canonical_name=entry.canonical_name,
                aliases=json.dumps(entry.aliases),
                macros_per_100g=json.dumps(entry.macros_per_100g),
                source=entry.source,
            )
            self._session.add(model)
        else:
            existing.aliases = json.dumps(entry.aliases)
            existing.macros_per_100g = json.dumps(entry.macros_per_100g)
            model = existing

        await self._session.flush()

        # Persist embedding in the vector store
        await self._vector_store.upsert(
            id=model.id,
            embedding=embedding,
            metadata={
                "canonical_name": model.canonical_name,
                "source": model.source,
            },
        )

        return self._model_to_entity(model)

    async def find_by_canonical_name(
        self,
        canonical_name: str,
        source: str,
    ) -> FoodCatalogEntry | None:
        stmt = select(FoodCatalogModel).where(
            FoodCatalogModel.canonical_name == canonical_name,
            FoodCatalogModel.source == source,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model is not None else None

    async def similarity_search(
        self,
        embedding: list[float],
        k: int,
    ) -> list[FoodCatalogEntry]:
        """Return catalog entries nearest to the given embedding.

        Delegates the actual ANN search to the vector store, then loads the
        full entries from the relational store by ID.
        """
        search_results: list[SearchResult] = await self._vector_store.similarity_search(
            embedding=embedding,
            k=k,
        )
        if not search_results:
            return []

        ids = [r.id for r in search_results]
        stmt = select(FoodCatalogModel).where(FoodCatalogModel.id.in_(ids))
        db_result = await self._session.execute(stmt)
        models_by_id = {m.id: m for m in db_result.scalars().all()}

        # Preserve similarity order from the vector store
        return [
            self._model_to_entity(models_by_id[r.id])
            for r in search_results
            if r.id in models_by_id
        ]
