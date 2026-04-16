"""Unit tests for embeddings providers.

All providers are mocked — no real API calls made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.infrastructure.embeddings import (
    DualEmbeddingsProvider,
    GeminiEmbeddingsProvider,
    OpenAIEmbeddingsProvider,
)


_FAKE_EMBEDDING = [0.1] * 1536


# ─────────────────────────────────────────────────────────────────────────────
# GeminiEmbeddingsProvider
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gemini_embed_returns_1536_dim_vector() -> None:
    mock_client = MagicMock()
    mock_client.aembed_query = AsyncMock(return_value=_FAKE_EMBEDDING)
    provider = GeminiEmbeddingsProvider.__new__(GeminiEmbeddingsProvider)
    provider._client = mock_client

    result = await provider.embed("test text")

    assert len(result) == 1536
    mock_client.aembed_query.assert_awaited_once_with("test text")


@pytest.mark.asyncio
async def test_gemini_embed_batch_returns_list_of_vectors() -> None:
    mock_client = MagicMock()
    mock_client.aembed_documents = AsyncMock(
        return_value=[_FAKE_EMBEDDING, _FAKE_EMBEDDING]
    )
    provider = GeminiEmbeddingsProvider.__new__(GeminiEmbeddingsProvider)
    provider._client = mock_client

    result = await provider.embed_batch(["text a", "text b"])

    assert len(result) == 2
    assert all(len(v) == 1536 for v in result)


# ─────────────────────────────────────────────────────────────────────────────
# OpenAIEmbeddingsProvider
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_openai_embed_returns_1536_dim_vector() -> None:
    mock_client = MagicMock()
    mock_client.aembed_query = AsyncMock(return_value=_FAKE_EMBEDDING)
    provider = OpenAIEmbeddingsProvider.__new__(OpenAIEmbeddingsProvider)
    provider._client = mock_client

    result = await provider.embed("test text")

    assert len(result) == 1536
    mock_client.aembed_query.assert_awaited_once_with("test text")


@pytest.mark.asyncio
async def test_openai_embed_batch_returns_list_of_vectors() -> None:
    mock_client = MagicMock()
    mock_client.aembed_documents = AsyncMock(return_value=[_FAKE_EMBEDDING])
    provider = OpenAIEmbeddingsProvider.__new__(OpenAIEmbeddingsProvider)
    provider._client = mock_client

    result = await provider.embed_batch(["only one"])

    assert len(result) == 1
    assert len(result[0]) == 1536


# ─────────────────────────────────────────────────────────────────────────────
# DualEmbeddingsProvider
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dual_uses_gemini_when_available() -> None:
    primary = MagicMock()
    primary.embed = AsyncMock(return_value=_FAKE_EMBEDDING)
    fallback = MagicMock()
    fallback.embed = AsyncMock(return_value=_FAKE_EMBEDDING)

    provider = DualEmbeddingsProvider(primary=primary, fallback=fallback)
    result = await provider.embed("hello")

    assert result == _FAKE_EMBEDDING
    primary.embed.assert_awaited_once_with("hello")
    fallback.embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_dual_falls_back_on_quota_error() -> None:
    primary = MagicMock()
    primary.embed = AsyncMock(side_effect=Exception("429 Resource exhausted"))
    fallback = MagicMock()
    fallback.embed = AsyncMock(return_value=_FAKE_EMBEDDING)

    provider = DualEmbeddingsProvider(primary=primary, fallback=fallback)
    result = await provider.embed("hello")

    assert result == _FAKE_EMBEDDING
    fallback.embed.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_dual_falls_back_on_service_unavailable() -> None:
    primary = MagicMock()
    primary.embed = AsyncMock(side_effect=Exception("503 Service Unavailable"))
    fallback = MagicMock()
    fallback.embed = AsyncMock(return_value=_FAKE_EMBEDDING)

    provider = DualEmbeddingsProvider(primary=primary, fallback=fallback)
    result = await provider.embed("hello")

    assert result == _FAKE_EMBEDDING


@pytest.mark.asyncio
async def test_dual_raises_when_both_providers_fail() -> None:
    primary = MagicMock()
    primary.embed = AsyncMock(side_effect=Exception("quota exceeded"))
    fallback = MagicMock()
    fallback.embed = AsyncMock(side_effect=Exception("openai down"))

    provider = DualEmbeddingsProvider(primary=primary, fallback=fallback)

    with pytest.raises(Exception, match="openai down"):
        await provider.embed("hello")


@pytest.mark.asyncio
async def test_dual_embed_batch_falls_back_on_primary_failure() -> None:
    primary = MagicMock()
    primary.embed_batch = AsyncMock(side_effect=Exception("quota exceeded"))
    fallback = MagicMock()
    fallback.embed_batch = AsyncMock(return_value=[_FAKE_EMBEDDING])

    provider = DualEmbeddingsProvider(primary=primary, fallback=fallback)
    result = await provider.embed_batch(["text"])

    assert len(result) == 1
    fallback.embed_batch.assert_awaited_once_with(["text"])
