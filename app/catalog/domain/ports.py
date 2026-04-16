"""Catalog domain ports."""

from __future__ import annotations

from typing import Protocol

from app.catalog.domain.entities import FoodCatalogEntry


class FoodCatalogRepositoryPort(Protocol):
    """Port for food catalog persistence."""

    async def upsert(
        self,
        entry: FoodCatalogEntry,
        embedding: list[float],
    ) -> FoodCatalogEntry:
        """Insert or update a catalog entry and its embedding vector."""
        ...

    async def find_by_canonical_name(
        self,
        canonical_name: str,
        source: str,
    ) -> FoodCatalogEntry | None:
        """Return the entry matching (canonical_name, source) or None."""
        ...

    async def similarity_search(
        self,
        embedding: list[float],
        k: int,
    ) -> list[FoodCatalogEntry]:
        """Return the k most similar catalog entries by vector distance."""
        ...
