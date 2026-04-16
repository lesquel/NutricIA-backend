"""Unit tests for CompositeRAGRetriever."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.chat.domain.entities import ConversationContext
from app.chat.infrastructure.rag_retriever import CompositeRAGRetriever
from app.shared.domain.ports import SearchResult


def _make_search_results(n: int = 2) -> list[SearchResult]:
    return [
        SearchResult(
            id=uuid.uuid4(),
            score=0.1 * i,
            metadata={"meal_id": str(uuid.uuid4()), "content_text": f"meal {i}"},
        )
        for i in range(n)
    ]


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_meal_vector_store() -> AsyncMock:
    vs = AsyncMock()
    vs.similarity_search.return_value = _make_search_results(3)
    return vs


@pytest.fixture
def mock_catalog_vector_store() -> AsyncMock:
    vs = AsyncMock()
    vs.similarity_search.return_value = _make_search_results(5)
    return vs


@pytest.fixture
def mock_embeddings() -> AsyncMock:
    emb = AsyncMock()
    emb.embed.return_value = [0.1] * 1536
    return emb


@pytest.fixture
def mock_user_food_profile_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_for_user.return_value = {
        "frequent_foods": ["rice", "chicken"],
        "avoided_tags": [],
    }
    return repo


@pytest.fixture
def mock_db_session() -> AsyncMock:
    session = AsyncMock()
    # Simulate last 5 meals query
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [
        MagicMock(
            id=uuid.uuid4(),
            name="Encebollado",
            calories=350,
            protein_g=25,
            carbs_g=40,
            fat_g=8,
            logged_at=MagicMock(isoformat=lambda: "2026-04-15T12:00:00"),
        )
    ]
    mock_result.scalars.return_value = mock_scalars
    session.execute.return_value = mock_result
    return session


class TestCompositeRAGRetriever:
    @pytest.mark.asyncio
    async def test_returns_conversation_context(
        self,
        user_id: uuid.UUID,
        mock_meal_vector_store: AsyncMock,
        mock_catalog_vector_store: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_user_food_profile_repo: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """retrieve_context returns a ConversationContext."""
        retriever = CompositeRAGRetriever(
            meal_vector_store=mock_meal_vector_store,
            catalog_vector_store=mock_catalog_vector_store,
            user_food_profile_repo=mock_user_food_profile_repo,
            embeddings_provider=mock_embeddings,
            db_session=mock_db_session,
        )
        ctx = await retriever.retrieve_context(
            user_id, "quiero una comida alta en proteína"
        )
        assert isinstance(ctx, ConversationContext)
        assert ctx.user_id == user_id

    @pytest.mark.asyncio
    async def test_all_sources_queried(
        self,
        user_id: uuid.UUID,
        mock_meal_vector_store: AsyncMock,
        mock_catalog_vector_store: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_user_food_profile_repo: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """All retrieval sources are called."""
        retriever = CompositeRAGRetriever(
            meal_vector_store=mock_meal_vector_store,
            catalog_vector_store=mock_catalog_vector_store,
            user_food_profile_repo=mock_user_food_profile_repo,
            embeddings_provider=mock_embeddings,
            db_session=mock_db_session,
        )
        await retriever.retrieve_context(user_id, "receta saludable")

        mock_embeddings.embed.assert_called_once()
        mock_meal_vector_store.similarity_search.assert_called_once()
        mock_catalog_vector_store.similarity_search.assert_called_once()
        mock_user_food_profile_repo.get_for_user.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_graceful_when_no_food_profile(
        self,
        user_id: uuid.UUID,
        mock_meal_vector_store: AsyncMock,
        mock_catalog_vector_store: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """No food profile is handled gracefully — user_food_profile is None."""
        repo_no_profile = AsyncMock()
        repo_no_profile.get_for_user.return_value = None

        retriever = CompositeRAGRetriever(
            meal_vector_store=mock_meal_vector_store,
            catalog_vector_store=mock_catalog_vector_store,
            user_food_profile_repo=repo_no_profile,
            embeddings_provider=mock_embeddings,
            db_session=mock_db_session,
        )
        ctx = await retriever.retrieve_context(user_id, "algo rico")
        assert isinstance(ctx, ConversationContext)
        assert ctx.user_food_profile is None

    @pytest.mark.asyncio
    async def test_recent_meals_populated(
        self,
        user_id: uuid.UUID,
        mock_meal_vector_store: AsyncMock,
        mock_catalog_vector_store: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_user_food_profile_repo: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """recent_meals is populated from the DB query."""
        retriever = CompositeRAGRetriever(
            meal_vector_store=mock_meal_vector_store,
            catalog_vector_store=mock_catalog_vector_store,
            user_food_profile_repo=mock_user_food_profile_repo,
            embeddings_provider=mock_embeddings,
            db_session=mock_db_session,
        )
        ctx = await retriever.retrieve_context(user_id, "comida de hoy")
        assert isinstance(ctx.recent_meals, list)

    @pytest.mark.asyncio
    async def test_real_profile_repo_passes_profile_to_context(
        self,
        user_id: uuid.UUID,
        mock_meal_vector_store: AsyncMock,
        mock_catalog_vector_store: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """When profile repo returns a real profile dict, it is included in context."""
        profile_data = {
            "frequent_foods": ["lenteja", "arroz"],
            "avoided_tags": ["spicy"],
        }
        real_repo = AsyncMock()
        real_repo.get_for_user.return_value = profile_data

        retriever = CompositeRAGRetriever(
            meal_vector_store=mock_meal_vector_store,
            catalog_vector_store=mock_catalog_vector_store,
            user_food_profile_repo=real_repo,
            embeddings_provider=mock_embeddings,
            db_session=mock_db_session,
        )
        ctx = await retriever.retrieve_context(user_id, "algo saludable")
        assert ctx.user_food_profile == profile_data

    @pytest.mark.asyncio
    async def test_none_profile_repo_returns_none_profile(
        self,
        user_id: uuid.UUID,
        mock_meal_vector_store: AsyncMock,
        mock_catalog_vector_store: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """When profile repo is injected as None (stub), user_food_profile is None."""

        class _NullRepo:
            async def get_for_user(self, _uid: uuid.UUID) -> None:
                return None

        retriever = CompositeRAGRetriever(
            meal_vector_store=mock_meal_vector_store,
            catalog_vector_store=mock_catalog_vector_store,
            user_food_profile_repo=_NullRepo(),
            embeddings_provider=mock_embeddings,
            db_session=mock_db_session,
        )
        ctx = await retriever.retrieve_context(user_id, "algo saludable")
        assert ctx.user_food_profile is None

    @pytest.mark.asyncio
    async def test_profile_repo_returning_object_is_converted_to_dict(
        self,
        user_id: uuid.UUID,
        mock_meal_vector_store: AsyncMock,
        mock_catalog_vector_store: AsyncMock,
        mock_embeddings: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """When profile repo returns a non-dict object, it is converted via vars()."""
        from dataclasses import dataclass

        @dataclass
        class _FakeProfile:
            frequent_foods: list[str]
            avoided_tags: list[str]

        profile_obj = _FakeProfile(frequent_foods=["quinua"], avoided_tags=[])
        repo = AsyncMock()
        repo.get_for_user.return_value = profile_obj

        retriever = CompositeRAGRetriever(
            meal_vector_store=mock_meal_vector_store,
            catalog_vector_store=mock_catalog_vector_store,
            user_food_profile_repo=repo,
            embeddings_provider=mock_embeddings,
            db_session=mock_db_session,
        )
        ctx = await retriever.retrieve_context(user_id, "algo proteico")
        assert isinstance(ctx.user_food_profile, dict)
        assert ctx.user_food_profile["frequent_foods"] == ["quinua"]
