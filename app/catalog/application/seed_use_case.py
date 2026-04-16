"""Catalog application — seed use case.

Seeds the food catalog from multiple external sources (USDA, Open Food Facts,
Ecuador curated list).  Running this multiple times is safe — entries are
upserted (dedup by canonical_name + source).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from app.catalog.domain.entities import FoodCatalogEntry
from app.catalog.infrastructure.sources.ecuador_source import EcuadorSource
from app.catalog.infrastructure.sources.openfoodfacts_source import OpenFoodFactsSource
from app.catalog.infrastructure.sources.usda_source import UsdaSource

if TYPE_CHECKING:
    from app.catalog.domain.ports import FoodCatalogRepositoryPort
    from app.shared.infrastructure.embeddings import EmbeddingsProviderPort

logger = logging.getLogger("nutricia.catalog.seed")


class SeedSource(str, Enum):
    """Supported seed data sources."""

    USDA = "usda"
    OPENFOODFACTS = "openfoodfacts"
    ECUADOR = "ecuador"


class SeedRunner:
    """Orchestrates seeding the food catalog from one or all sources.

    Parameters
    ----------
    repo:
        Any implementation of FoodCatalogRepositoryPort.
    embeddings_provider:
        Any implementation of EmbeddingsProviderPort.
    """

    def __init__(
        self,
        repo: "FoodCatalogRepositoryPort",
        embeddings_provider: "EmbeddingsProviderPort",
    ) -> None:
        self._repo = repo
        self._embeddings = embeddings_provider

    async def run(self, source: SeedSource | None = None) -> None:
        """Seed the catalog.

        Parameters
        ----------
        source:
            If given, only this source is processed.
            If None (default), all sources are processed.
        """
        sources_to_run: list[tuple[SeedSource, object]] = []

        if source is None or source == SeedSource.ECUADOR:
            sources_to_run.append((SeedSource.ECUADOR, EcuadorSource()))

        if source is None or source == SeedSource.USDA:
            sources_to_run.append((SeedSource.USDA, UsdaSource()))

        if source is None or source == SeedSource.OPENFOODFACTS:
            sources_to_run.append((SeedSource.OPENFOODFACTS, OpenFoodFactsSource()))

        for source_enum, source_impl in sources_to_run:
            await self._run_source(source_enum, source_impl)

    async def _run_source(
        self,
        source_enum: SeedSource,
        source_impl: object,
    ) -> None:
        """Process a single source, catching and logging any errors."""
        try:
            entries: list[FoodCatalogEntry] = await source_impl.fetch()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning(
                "Source %s failed to fetch entries: %s — skipping",
                source_enum.value,
                exc,
            )
            return

        logger.info(
            "Source %s returned %d entries — upserting...",
            source_enum.value,
            len(entries),
        )

        for entry in entries:
            try:
                embedding = await self._embeddings.embed(
                    f"{entry.canonical_name}, "
                    f"calories: {entry.macros_per_100g.get('calories', 0)}, "
                    f"protein: {entry.macros_per_100g.get('protein_g', 0)}g, "
                    f"source: {entry.source}"
                )
                await self._repo.upsert(entry, embedding)
            except Exception as exc:
                logger.warning(
                    "Failed to upsert entry '%s' from %s: %s — skipping",
                    entry.canonical_name,
                    source_enum.value,
                    exc,
                )

        logger.info("Source %s seeding complete.", source_enum.value)
