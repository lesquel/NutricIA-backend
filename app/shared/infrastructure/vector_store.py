"""Shared infrastructure — Vector store adapters and factory.

InMemoryVectorStoreAdapter
    Pure-Python cosine-distance store for unit tests.
    No dependencies beyond the stdlib.

PgVectorAdapter
    Production adapter backed by pgvector via SQLAlchemy text() queries.
    Requires the `vector` extension and the `pgvector` Python package.
    Pass the AsyncSession factory and the target table name at construction.
"""

from __future__ import annotations

import logging
import math
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.domain.ports import SearchResult

logger = logging.getLogger("nutricia.shared.vector_store")


# ─────────────────────────────────────────────────────────────────────────────
# In-memory adapter (used in tests)
# ─────────────────────────────────────────────────────────────────────────────


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Return cosine distance (0 = identical, 2 = opposite) between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


class InMemoryVectorStoreAdapter:
    """In-memory vector store for unit tests.

    Stores entries as {id: (embedding, metadata)} and implements
    exact cosine distance search.
    """

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, tuple[list[float], dict[str, Any]]] = {}

    async def upsert(
        self,
        id: uuid.UUID,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        self._store[id] = (embedding, metadata)

    async def similarity_search(
        self,
        embedding: list[float],
        k: int,
        filter: dict | None = None,
    ) -> list[SearchResult]:
        if not self._store:
            return []

        results: list[SearchResult] = []
        for entry_id, (entry_emb, entry_meta) in self._store.items():
            if filter:
                if not all(entry_meta.get(fk) == fv for fk, fv in filter.items()):
                    continue
            score = _cosine_distance(embedding, entry_emb)
            results.append(SearchResult(id=entry_id, score=score, metadata=entry_meta))

        results.sort(key=lambda r: r.score)
        return results[:k]

    async def delete(self, id: uuid.UUID) -> None:
        self._store.pop(id, None)


# ─────────────────────────────────────────────────────────────────────────────
# PgVector adapter (production — postgres only)
# ─────────────────────────────────────────────────────────────────────────────


class PgVectorAdapter:
    """Production vector store backed by pgvector.

    Parameters
    ----------
    session_factory:
        An async_sessionmaker or any callable that returns an AsyncSession
        context manager.
    table_name:
        The table to operate on (e.g. "food_catalog" or "meal_embeddings").
        The table must have columns: id (UUID PK), embedding (VECTOR), and
        whatever additional columns you store as metadata.
    id_column:
        Name of the primary key column (default "id").
    embedding_column:
        Name of the vector column (default "embedding").
    metadata_columns:
        Sequence of column names to SELECT and include in SearchResult.metadata.
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        table_name: str,
        id_column: str = "id",
        embedding_column: str = "embedding",
        metadata_columns: list[str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._table = table_name
        self._id_col = id_column
        self._emb_col = embedding_column
        self._meta_cols = metadata_columns or []

    def _format_vec(self, embedding: list[float]) -> str:
        """Format a Python list as a pgvector literal: '[0.1,0.2,...]'."""
        return "[" + ",".join(str(v) for v in embedding) + "]"

    async def upsert(
        self,
        id: uuid.UUID,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        vec_literal = self._format_vec(embedding)
        # Build column list dynamically
        meta_keys = list(metadata.keys())
        all_cols = [self._id_col, self._emb_col] + meta_keys
        col_list = ", ".join(all_cols)
        val_placeholders = ", ".join(
            f":{c}" if c not in (self._emb_col,) else f":{c}::vector" for c in all_cols
        )
        update_set = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in [self._emb_col] + meta_keys
        )
        sql = text(
            f"""
            INSERT INTO {self._table} ({col_list})
            VALUES ({val_placeholders})
            ON CONFLICT ({self._id_col}) DO UPDATE SET {update_set}
            """
        )
        params: dict[str, Any] = {
            self._id_col: id,
            self._emb_col: vec_literal,
            **metadata,
        }
        async with self._session_factory() as session:
            await session.execute(sql, params)
            await session.commit()

    async def similarity_search(
        self,
        embedding: list[float],
        k: int,
        filter: dict | None = None,
    ) -> list[SearchResult]:
        vec_literal = self._format_vec(embedding)
        meta_select = ", ".join(self._meta_cols) + ", " if self._meta_cols else ""
        where_clause = ""
        where_params: dict[str, Any] = {}
        if filter:
            conditions = []
            for i, (fk, fv) in enumerate(filter.items()):
                param_name = f"filter_{i}"
                conditions.append(f"{fk} = :{param_name}")
                where_params[param_name] = fv
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = text(
            f"""
            SELECT {self._id_col},
                   {meta_select}
                   {self._emb_col} <-> :query_vec::vector AS score
            FROM {self._table}
            {where_clause}
            ORDER BY score ASC
            LIMIT :k
            """
        )
        params = {"query_vec": vec_literal, "k": k, **where_params}

        async with self._session_factory() as session:
            rows = (await session.execute(sql, params)).fetchall()

        results: list[SearchResult] = []
        for row in rows:
            row_dict = row._mapping
            entry_id = row_dict[self._id_col]
            score = float(row_dict["score"])
            meta = {col: row_dict[col] for col in self._meta_cols if col in row_dict}
            results.append(SearchResult(id=entry_id, score=score, metadata=meta))
        return results

    async def delete(self, id: uuid.UUID) -> None:
        sql = text(f"DELETE FROM {self._table} WHERE {self._id_col} = :id")
        async with self._session_factory() as session:
            await session.execute(sql, {"id": id})
            await session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Env-driven factory
# ─────────────────────────────────────────────────────────────────────────────


def get_vector_store(table_name: str) -> "InMemoryVectorStoreAdapter | PgVectorAdapter":
    """Return the appropriate VectorStorePort based on settings.

    Reads ``settings.vector_store_backend``:
    - ``"in_memory"`` → ``InMemoryVectorStoreAdapter`` (default; zero dependencies)
    - ``"pgvector"`` → ``PgVectorAdapter`` if ``database_url`` starts with
      ``postgresql``; falls back to ``InMemoryVectorStoreAdapter`` with a warning
      if the URL is not postgres (e.g. sqlite in dev).

    Parameters
    ----------
    table_name:
        The table name to pass to ``PgVectorAdapter`` (e.g. ``"meal_embeddings"``).
    """
    from app.config import settings

    backend = settings.vector_store_backend
    db_url = settings.database_url

    if backend == "pgvector":
        if db_url.startswith("postgresql"):
            from app.database import async_session_factory  # type: ignore[import-not-found]

            return PgVectorAdapter(
                session_factory=async_session_factory,
                table_name=table_name,
            )
        logger.warning(
            "vector_store_backend='pgvector' but database_url is not postgresql "
            "('%s'). Falling back to InMemoryVectorStoreAdapter.",
            db_url[:40],
        )
        return InMemoryVectorStoreAdapter()

    # Default: in_memory
    return InMemoryVectorStoreAdapter()
