"""Unit tests for FoodCatalogRepositoryImpl.

Uses in-memory SQLite via the shared conftest db_session fixture.
Vector store is mocked — repository behaviour is under test, not the store.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.domain.entities import FoodCatalogEntry
from app.catalog.domain import CatalogEntryNotFoundError, DuplicateCanonicalNameError
from app.catalog.infrastructure.repository import FoodCatalogRepositoryImpl


# ─── helpers ─────────────────────────────────────────────────────────────────


def _make_entry(
    canonical_name: str = "Chicken Breast",
    source: str = "usda",
    entry_id: uuid.UUID | None = None,
) -> FoodCatalogEntry:
    return FoodCatalogEntry(
        id=entry_id or uuid.uuid4(),
        canonical_name=canonical_name,
        aliases=["pollo", "chicken"],
        macros_per_100g={
            "calories": 165.0,
            "protein_g": 31.0,
            "carbs_g": 0.0,
            "fat_g": 3.6,
        },
        source=source,
    )


def _mock_vector_store() -> MagicMock:
    store = MagicMock()
    store.upsert = AsyncMock()
    store.similarity_search = AsyncMock(return_value=[])
    store.delete = AsyncMock()
    return store


# ─── tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_creates_new_entry(db_session: AsyncSession) -> None:
    store = _mock_vector_store()
    repo = FoodCatalogRepositoryImpl(session=db_session, vector_store=store)
    entry = _make_entry()

    result = await repo.upsert(entry, embedding=[0.1] * 4)

    assert result.id == entry.id
    assert result.canonical_name == entry.canonical_name


@pytest.mark.asyncio
async def test_upsert_updates_existing_entry(db_session: AsyncSession) -> None:
    """Upserting the same (canonical_name, source) must update, not duplicate."""
    store = _mock_vector_store()
    repo = FoodCatalogRepositoryImpl(session=db_session, vector_store=store)
    entry = _make_entry()

    await repo.upsert(entry, embedding=[0.1] * 4)

    updated = FoodCatalogEntry(
        id=entry.id,
        canonical_name=entry.canonical_name,
        aliases=["updated alias"],
        macros_per_100g={**entry.macros_per_100g, "calories": 170.0},
        source=entry.source,
    )
    result = await repo.upsert(updated, embedding=[0.2] * 4)

    assert result.macros_per_100g["calories"] == 170.0
    # vector store upsert must have been called for each upsert
    assert store.upsert.await_count == 2


@pytest.mark.asyncio
async def test_find_by_canonical_name_returns_entry(db_session: AsyncSession) -> None:
    store = _mock_vector_store()
    repo = FoodCatalogRepositoryImpl(session=db_session, vector_store=store)
    entry = _make_entry()
    await repo.upsert(entry, embedding=[0.1] * 4)

    found = await repo.find_by_canonical_name(entry.canonical_name, entry.source)

    assert found is not None
    assert found.canonical_name == entry.canonical_name
    assert found.source == entry.source


@pytest.mark.asyncio
async def test_find_by_canonical_name_returns_none_when_missing(
    db_session: AsyncSession,
) -> None:
    store = _mock_vector_store()
    repo = FoodCatalogRepositoryImpl(session=db_session, vector_store=store)

    found = await repo.find_by_canonical_name("nonexistent food", "usda")

    assert found is None


@pytest.mark.asyncio
async def test_find_by_canonical_name_filters_by_source(
    db_session: AsyncSession,
) -> None:
    store = _mock_vector_store()
    repo = FoodCatalogRepositoryImpl(session=db_session, vector_store=store)
    entry_usda = _make_entry(source="usda")
    entry_openfood = _make_entry(
        canonical_name=entry_usda.canonical_name, source="openfoodfacts"
    )
    await repo.upsert(entry_usda, embedding=[0.1] * 4)
    await repo.upsert(entry_openfood, embedding=[0.2] * 4)

    found = await repo.find_by_canonical_name(entry_usda.canonical_name, "usda")

    assert found is not None
    assert found.source == "usda"


@pytest.mark.asyncio
async def test_similarity_search_delegates_to_vector_store(
    db_session: AsyncSession,
) -> None:
    """similarity_search must delegate to the vector store and map results."""
    from app.shared.domain.ports import SearchResult

    entry = _make_entry()
    mock_result = SearchResult(
        id=entry.id, score=0.05, metadata={"canonical_name": entry.canonical_name}
    )
    store = _mock_vector_store()
    store.similarity_search = AsyncMock(return_value=[mock_result])

    repo = FoodCatalogRepositoryImpl(session=db_session, vector_store=store)
    await repo.upsert(entry, embedding=[0.1] * 4)

    results = await repo.similarity_search(embedding=[0.1] * 4, k=5)

    store.similarity_search.assert_awaited_once()
    assert len(results) == 1
