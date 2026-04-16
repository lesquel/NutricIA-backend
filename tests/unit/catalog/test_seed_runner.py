"""Unit tests for catalog seed runner."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.catalog.application.seed_use_case import SeedRunner, SeedSource
from app.catalog.domain.entities import FoodCatalogEntry


def _make_entry(name: str, source: str) -> FoodCatalogEntry:
    return FoodCatalogEntry(
        id=uuid.uuid4(),
        canonical_name=name,
        aliases=[],
        macros_per_100g={"calories": 100, "protein_g": 5, "carbs_g": 15, "fat_g": 2},
        source=source,
    )


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    # upsert returns the entry passed in
    repo.upsert.side_effect = lambda entry, embedding: entry
    return repo


@pytest.fixture
def mock_embeddings() -> AsyncMock:
    provider = AsyncMock()
    provider.embed.return_value = [0.1] * 1536
    return provider


@pytest.fixture
def mock_ecuador_entries() -> list[FoodCatalogEntry]:
    return [
        _make_entry("Encebollado", "ecuador"),
        _make_entry("Llapingachos", "ecuador"),
    ]


@pytest.fixture
def mock_usda_entries() -> list[FoodCatalogEntry]:
    return [_make_entry("Chicken Breast", "usda"), _make_entry("Brown Rice", "usda")]


@pytest.fixture
def mock_off_entries() -> list[FoodCatalogEntry]:
    return [_make_entry("Oat Milk", "openfoodfacts")]


class TestSeedRunnerRunAll:
    @pytest.mark.asyncio
    async def test_run_all_calls_embedding_for_each_entry(
        self,
        mock_repo: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_ecuador_entries: list[FoodCatalogEntry],
        mock_usda_entries: list[FoodCatalogEntry],
        mock_off_entries: list[FoodCatalogEntry],
    ) -> None:
        """run(all) calls embed once per entry across all sources."""
        with (
            patch(
                "app.catalog.application.seed_use_case.EcuadorSource.fetch",
                return_value=mock_ecuador_entries,
            ),
            patch(
                "app.catalog.application.seed_use_case.UsdaSource.fetch",
                return_value=mock_usda_entries,
            ),
            patch(
                "app.catalog.application.seed_use_case.OpenFoodFactsSource.fetch",
                return_value=mock_off_entries,
            ),
        ):
            runner = SeedRunner(repo=mock_repo, embeddings_provider=mock_embeddings)
            await runner.run()

        total = (
            len(mock_ecuador_entries) + len(mock_usda_entries) + len(mock_off_entries)
        )
        assert mock_embeddings.embed.call_count == total

    @pytest.mark.asyncio
    async def test_run_all_upserts_each_entry(
        self,
        mock_repo: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_ecuador_entries: list[FoodCatalogEntry],
        mock_usda_entries: list[FoodCatalogEntry],
        mock_off_entries: list[FoodCatalogEntry],
    ) -> None:
        """run(all) calls repo.upsert for every entry."""
        with (
            patch(
                "app.catalog.application.seed_use_case.EcuadorSource.fetch",
                return_value=mock_ecuador_entries,
            ),
            patch(
                "app.catalog.application.seed_use_case.UsdaSource.fetch",
                return_value=mock_usda_entries,
            ),
            patch(
                "app.catalog.application.seed_use_case.OpenFoodFactsSource.fetch",
                return_value=mock_off_entries,
            ),
        ):
            runner = SeedRunner(repo=mock_repo, embeddings_provider=mock_embeddings)
            await runner.run()

        total = (
            len(mock_ecuador_entries) + len(mock_usda_entries) + len(mock_off_entries)
        )
        assert mock_repo.upsert.call_count == total

    @pytest.mark.asyncio
    async def test_run_single_source(
        self,
        mock_repo: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_ecuador_entries: list[FoodCatalogEntry],
    ) -> None:
        """run(ecuador) only processes Ecuador source."""
        with patch(
            "app.catalog.application.seed_use_case.EcuadorSource.fetch",
            return_value=mock_ecuador_entries,
        ):
            runner = SeedRunner(repo=mock_repo, embeddings_provider=mock_embeddings)
            await runner.run(source=SeedSource.ECUADOR)

        assert mock_embeddings.embed.call_count == len(mock_ecuador_entries)
        assert mock_repo.upsert.call_count == len(mock_ecuador_entries)


class TestSeedRunnerDedup:
    @pytest.mark.asyncio
    async def test_rerunning_same_source_upserts_not_duplicates(
        self,
        mock_repo: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_ecuador_entries: list[FoodCatalogEntry],
    ) -> None:
        """Re-running same source calls upsert (idempotent) — no duplicates."""
        with patch(
            "app.catalog.application.seed_use_case.EcuadorSource.fetch",
            return_value=mock_ecuador_entries,
        ):
            runner = SeedRunner(repo=mock_repo, embeddings_provider=mock_embeddings)
            await runner.run(source=SeedSource.ECUADOR)
            await runner.run(source=SeedSource.ECUADOR)

        # upsert called twice (once per run * entries) — repo handles dedup
        assert mock_repo.upsert.call_count == len(mock_ecuador_entries) * 2


class TestSeedRunnerGracefulFailure:
    @pytest.mark.asyncio
    async def test_source_failure_skipped_gracefully(
        self,
        mock_repo: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_ecuador_entries: list[FoodCatalogEntry],
    ) -> None:
        """If one source raises, it is skipped — others still processed."""
        with (
            patch(
                "app.catalog.application.seed_use_case.EcuadorSource.fetch",
                return_value=mock_ecuador_entries,
            ),
            patch(
                "app.catalog.application.seed_use_case.UsdaSource.fetch",
                side_effect=Exception("API error"),
            ),
            patch(
                "app.catalog.application.seed_use_case.OpenFoodFactsSource.fetch",
                return_value=[],
            ),
        ):
            runner = SeedRunner(repo=mock_repo, embeddings_provider=mock_embeddings)
            # Must not raise
            await runner.run()

        # Only ecuador entries processed
        assert mock_repo.upsert.call_count == len(mock_ecuador_entries)

    @pytest.mark.asyncio
    async def test_empty_source_is_noop(
        self,
        mock_repo: AsyncMock,
        mock_embeddings: AsyncMock,
    ) -> None:
        """Source returning empty list results in no upsert calls."""
        with (
            patch(
                "app.catalog.application.seed_use_case.EcuadorSource.fetch",
                return_value=[],
            ),
            patch(
                "app.catalog.application.seed_use_case.UsdaSource.fetch",
                return_value=[],
            ),
            patch(
                "app.catalog.application.seed_use_case.OpenFoodFactsSource.fetch",
                return_value=[],
            ),
        ):
            runner = SeedRunner(repo=mock_repo, embeddings_provider=mock_embeddings)
            await runner.run()

        assert mock_repo.upsert.call_count == 0
        assert mock_embeddings.embed.call_count == 0
