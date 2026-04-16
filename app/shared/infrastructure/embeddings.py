"""Shared infrastructure — Embeddings providers.

The `EmbeddingsProviderPort` Protocol lives in `app.shared.domain.ports`;
this module provides three concrete implementations:

GeminiEmbeddingsProvider
    Uses Google Generative AI (text-embedding-004, output_dimensionality=1536).

OpenAIEmbeddingsProvider
    Uses OpenAI (text-embedding-3-small, dimensions=1536).

DualEmbeddingsProvider
    Primary=Gemini with OpenAI fallback. Mirrors the multi-provider pattern
    in meals/infrastructure/ai_providers.py.
"""

from __future__ import annotations

import logging

# Re-export the port from domain so existing imports remain stable while the
# canonical definition lives in `shared/domain/ports.py`.
from app.shared.domain.ports import EmbeddingsProviderPort

__all__ = [
    "EmbeddingsProviderPort",
    "GeminiEmbeddingsProvider",
    "OpenAIEmbeddingsProvider",
    "DualEmbeddingsProvider",
]

logger = logging.getLogger("nutricia.embeddings")


# ─────────────────────────────────────────────────────────────────────────────
# Gemini provider
# ─────────────────────────────────────────────────────────────────────────────


class GeminiEmbeddingsProvider:
    """Embeddings via Google Generative AI (text-embedding-004)."""

    def __init__(self, api_key: str) -> None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self._client = GoogleGenerativeAIEmbeddings(  # type: ignore[call-arg]
            model="models/text-embedding-004",
            google_api_key=api_key,
            task_type="retrieval_document",
        )

    async def embed(self, text: str) -> list[float]:
        return list(await self._client.aembed_query(text))

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = await self._client.aembed_documents(texts)
        return [list(v) for v in results]


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI provider
# ─────────────────────────────────────────────────────────────────────────────


class OpenAIEmbeddingsProvider:
    """Embeddings via OpenAI (text-embedding-3-small, 1536 dims)."""

    def __init__(self, api_key: str) -> None:
        from langchain_openai import OpenAIEmbeddings

        self._client = OpenAIEmbeddings(  # type: ignore[call-arg]
            model="text-embedding-3-small",
            dimensions=1536,
            openai_api_key=api_key,
        )

    async def embed(self, text: str) -> list[float]:
        return list(await self._client.aembed_query(text))

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = await self._client.aembed_documents(texts)
        return [list(v) for v in results]


# ─────────────────────────────────────────────────────────────────────────────
# Dual provider (Gemini primary + OpenAI fallback)
# ─────────────────────────────────────────────────────────────────────────────


def _is_transient_error(exc: BaseException) -> bool:
    """Return True for quota / rate-limit / availability errors."""
    msg = str(exc).lower()
    return any(
        kw in msg
        for kw in (
            "429",
            "quota",
            "resource exhausted",
            "rate limit",
            "unavailable",
            "503",
            "502",
            "overloaded",
        )
    )


class DualEmbeddingsProvider:
    """Primary + fallback embeddings provider.

    Attempts the primary provider first.  On any transient error (quota,
    rate-limit, service unavailability) falls through to the fallback.
    If the fallback also fails, propagates the fallback exception.

    Non-transient primary errors (e.g. invalid input) are also retried on the
    fallback so callers always receive a best-effort response.
    """

    def __init__(
        self,
        primary: EmbeddingsProviderPort,
        fallback: EmbeddingsProviderPort,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    async def embed(self, text: str) -> list[float]:
        try:
            return await self._primary.embed(text)
        except Exception as exc:
            logger.warning(
                "Primary embeddings provider failed (%s), falling back.", exc
            )
            return await self._fallback.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            return await self._primary.embed_batch(texts)
        except Exception as exc:
            logger.warning(
                "Primary embeddings provider failed on batch (%s), falling back.", exc
            )
            return await self._fallback.embed_batch(texts)
