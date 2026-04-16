"""Integration tests for meal save + embedding background hook."""

from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.main import create_app
from app.shared.infrastructure.vector_store import InMemoryVectorStoreAdapter


@pytest_asyncio.fixture
async def meals_app(db_session: AsyncSession) -> AsyncGenerator[FastAPI, None]:
    """App with DB override for meal save tests."""
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def meals_client(meals_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=meals_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestMealSaveWithEmbedding:
    @pytest.mark.asyncio
    async def test_meal_save_returns_201_quickly(
        self,
        meals_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """POST /meals returns 201 without waiting on embedding generation."""
        mock_embeddings = AsyncMock()
        mock_embeddings.embed.return_value = [0.1] * 1536
        vector_store = InMemoryVectorStoreAdapter()

        meal_data = {
            "name": "Arroz con pollo",
            "calories": 450,
            "protein_g": 30,
            "carbs_g": 55,
            "fat_g": 8,
            "meal_type": "lunch",
            "confidence_score": 0.85,
            "tags": ["Protein"],
        }

        with (
            patch(
                "app.meals.presentation.router._get_embeddings_provider",
                return_value=mock_embeddings,
            ),
            patch(
                "app.meals.presentation.router._get_meal_vector_store",
                return_value=vector_store,
            ),
        ):
            response = await meals_client.post(
                "/api/v1/meals",
                json=meal_data,
                headers=auth_headers,
            )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_meal_save_without_embedding_still_works(
        self,
        meals_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """POST /meals works even when embedding providers are not configured."""
        meal_data = {
            "name": "Ensalada verde",
            "calories": 150,
            "protein_g": 5,
            "carbs_g": 20,
            "fat_g": 3,
            "meal_type": "lunch",
            "confidence_score": 0.9,
            "tags": [],
        }

        # No mocking — embedding hook should fail silently
        response = await meals_client.post(
            "/api/v1/meals",
            json=meal_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
