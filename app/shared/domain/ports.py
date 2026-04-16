"""Shared domain ports — interfaces that infrastructure adapters must implement."""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


@dataclass
class SearchResult:
    """A single result from a vector similarity search."""

    id: UUID
    score: float
    metadata: dict = field(default_factory=dict)


class VectorStorePort(Protocol):
    """Port for vector store operations.

    Implementations must support upsert, similarity search, and delete.
    The same adapter can serve multiple tables (food_catalog, meal_embeddings)
    by parameterising the table name at construction time.
    """

    async def upsert(
        self,
        id: UUID,
        embedding: list[float],
        metadata: dict,
    ) -> None:
        """Insert or replace a vector entry."""
        ...

    async def similarity_search(
        self,
        embedding: list[float],
        k: int,
        filter: dict | None = None,
    ) -> list[SearchResult]:
        """Return the k nearest neighbours ordered by ascending distance."""
        ...

    async def delete(self, id: UUID) -> None:
        """Remove a vector entry by ID."""
        ...


class EmbeddingsProviderPort(Protocol):
    """Port for embedding text into fixed-size float vectors.

    Implementations live in `shared/infrastructure/embeddings.py`
    (Gemini, OpenAI, Dual). Vector dimension is fixed at 1536 to match
    the pgvector column definition.
    """

    async def embed(self, text: str) -> list[float]:
        """Return a single 1536-dimensional embedding vector."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return a batch of 1536-dimensional embedding vectors."""
        ...
