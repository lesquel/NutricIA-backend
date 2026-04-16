"""Unit tests for vector store adapters.

All tests run against InMemoryVectorStoreAdapter — no pgvector required.
Integration tests that require postgres are marked @pytest.mark.requires_postgres
and skipped in CI by default.
"""

import math
import uuid
from typing import Any
from unittest.mock import patch

import pytest

from app.shared.domain.ports import SearchResult
from app.shared.infrastructure.vector_store import (
    InMemoryVectorStoreAdapter,
    PgVectorAdapter,
    get_vector_store,
)


def _vec(dim: int = 4, val: float = 1.0) -> list[float]:
    """Helper: returns a normalised vector of given dimension."""
    v = [val] * dim
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


@pytest.fixture
def store() -> InMemoryVectorStoreAdapter:
    return InMemoryVectorStoreAdapter()


@pytest.mark.asyncio
async def test_upsert_then_search_returns_entry(
    store: InMemoryVectorStoreAdapter,
) -> None:
    """upsert followed by similarity_search must return the entry."""
    entry_id = uuid.uuid4()
    embedding = _vec(4)
    await store.upsert(entry_id, embedding, {"name": "chicken"})

    results = await store.similarity_search(embedding, k=1)

    assert len(results) == 1
    assert results[0].id == entry_id
    assert isinstance(results[0].score, float)


@pytest.mark.asyncio
async def test_similarity_search_returns_k_results(
    store: InMemoryVectorStoreAdapter,
) -> None:
    """similarity_search must return at most k results."""
    for i in range(5):
        await store.upsert(uuid.uuid4(), _vec(4, float(i + 1)), {"i": i})

    results = await store.similarity_search(_vec(4, 1.0), k=3)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_similarity_search_results_ordered_by_score(
    store: InMemoryVectorStoreAdapter,
) -> None:
    """Results must be ordered ascending by distance (closest first)."""
    query = _vec(4, 1.0)

    # identical to query → distance 0
    close_id = uuid.uuid4()
    await store.upsert(close_id, query, {"label": "close"})

    # orthogonal → maximum cosine distance
    far_id = uuid.uuid4()
    far_vec = [0.0, 0.0, 0.0, 1.0]
    far_vec_norm = math.sqrt(sum(x * x for x in far_vec))
    far_vec = [x / far_vec_norm for x in far_vec]
    await store.upsert(far_id, far_vec, {"label": "far"})

    results = await store.similarity_search(query, k=2)

    assert results[0].id == close_id
    assert results[0].score <= results[1].score


@pytest.mark.asyncio
async def test_upsert_overwrites_existing_entry(
    store: InMemoryVectorStoreAdapter,
) -> None:
    """Calling upsert with an existing id must overwrite metadata and embedding."""
    entry_id = uuid.uuid4()
    await store.upsert(entry_id, _vec(4, 1.0), {"label": "original"})
    await store.upsert(entry_id, _vec(4, 2.0), {"label": "updated"})

    results = await store.similarity_search(_vec(4, 2.0), k=1)
    assert results[0].metadata["label"] == "updated"


@pytest.mark.asyncio
async def test_delete_removes_entry(store: InMemoryVectorStoreAdapter) -> None:
    """delete must remove the entry so it no longer appears in searches."""
    entry_id = uuid.uuid4()
    await store.upsert(entry_id, _vec(4), {"label": "to_delete"})
    await store.delete(entry_id)

    results = await store.similarity_search(_vec(4), k=10)
    ids = [r.id for r in results]
    assert entry_id not in ids


@pytest.mark.asyncio
async def test_delete_nonexistent_is_noop(store: InMemoryVectorStoreAdapter) -> None:
    """delete on a non-existent id must not raise."""
    await store.delete(uuid.uuid4())  # should not raise


@pytest.mark.asyncio
async def test_similarity_search_empty_store_returns_empty(
    store: InMemoryVectorStoreAdapter,
) -> None:
    results = await store.similarity_search(_vec(4), k=5)
    assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# get_vector_store factory
# ─────────────────────────────────────────────────────────────────────────────


class TestGetVectorStoreFactory:
    def test_returns_in_memory_when_backend_is_in_memory(self) -> None:
        """get_vector_store returns InMemoryVectorStoreAdapter for in_memory backend."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.vector_store_backend = "in_memory"
            mock_settings.database_url = "sqlite+aiosqlite:///./test.db"
            result = get_vector_store("meal_embeddings")
        assert isinstance(result, InMemoryVectorStoreAdapter)

    def test_returns_pgvector_when_backend_pgvector_and_postgres_url(self) -> None:
        """get_vector_store returns PgVectorAdapter when backend=pgvector + postgres URL."""
        import sys

        fake_session_factory = object()
        fake_db_module = type(sys)("app.database")
        fake_db_module.async_session_factory = fake_session_factory  # type: ignore[attr-defined]

        with (
            patch("app.config.settings") as mock_settings,
            patch.dict("sys.modules", {"app.database": fake_db_module}),
        ):
            mock_settings.vector_store_backend = "pgvector"
            mock_settings.database_url = "postgresql+asyncpg://user:pass@localhost/db"
            result = get_vector_store("food_catalog")

        assert isinstance(result, PgVectorAdapter)

    def test_fallback_to_in_memory_when_pgvector_but_sqlite_url(self) -> None:
        """get_vector_store falls back to InMemory when backend=pgvector but URL is sqlite."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.vector_store_backend = "pgvector"
            mock_settings.database_url = "sqlite+aiosqlite:///./nutricia.db"
            result = get_vector_store("meal_embeddings")
        assert isinstance(result, InMemoryVectorStoreAdapter)

    def test_fallback_logs_warning_for_non_postgres_url(self, caplog: Any) -> None:
        """A warning is logged when pgvector is requested but URL is not postgres."""
        import logging

        with (
            patch("app.config.settings") as mock_settings,
            caplog.at_level(logging.WARNING, logger="nutricia.shared.vector_store"),
        ):
            mock_settings.vector_store_backend = "pgvector"
            mock_settings.database_url = "sqlite+aiosqlite:///./nutricia.db"
            get_vector_store("meal_embeddings")

        assert any(
            "Falling back" in r.message or "fallback" in r.message.lower()
            for r in caplog.records
        )
