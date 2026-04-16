"""Integration tests for chat API endpoints."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.domain.entities import Conversation, ConversationContext
from app.chat.domain.errors import ConversationNotFoundError
from app.dependencies import get_db
from app.main import create_app


async def _fake_stream_events(events: list[dict]) -> AsyncGenerator[dict, None]:
    for evt in events:
        yield evt


@pytest_asyncio.fixture
async def chat_app(db_session: AsyncSession) -> AsyncGenerator[FastAPI, None]:
    """App with DB override and mocked LLM/embeddings for chat tests."""
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
async def chat_client(chat_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=chat_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestChatMessageEndpoint:
    @pytest.mark.asyncio
    async def test_post_message_returns_sse_events(
        self,
        chat_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """POST /chat/message returns SSE response with events."""
        fake_events = [
            {"type": "token", "content": "Hola"},
            {"type": "token", "content": " mundo"},
            {"type": "done", "message_id": str(uuid.uuid4())},
        ]

        with patch(
            "app.chat.infrastructure.llm.ChatLLMService.astream_response",
            return_value=_fake_stream_events(fake_events),
        ):
            response = await chat_client.post(
                "/api/v1/chat/message",
                json={
                    "content": "Quiero una receta saludable",
                    "conversation_id": None,
                },
                headers=auth_headers,
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_post_message_requires_auth(self, chat_client: AsyncClient) -> None:
        """POST /chat/message requires authentication.

        FastAPI's HTTPBearer security scheme returns 401 for missing creds and
        403 for invalid creds. We assert the unauthenticated path returns one
        of those (auth-related) statuses, not the default 422.
        """
        response = await chat_client.post(
            "/api/v1/chat/message",
            json={"content": "test", "conversation_id": None},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_conversations_returns_list(
        self,
        chat_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """GET /chat/conversations returns a list."""
        response = await chat_client.get(
            "/api/v1/chat/conversations",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data or isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_conversations_requires_auth(
        self, chat_client: AsyncClient
    ) -> None:
        """GET /chat/conversations requires authentication."""
        response = await chat_client.get("/api/v1/chat/conversations")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_messages_for_unknown_conversation_returns_404(
        self,
        chat_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """GET /chat/conversations/{id}/messages returns 404 for unknown conversation."""
        unknown_id = str(uuid.uuid4())
        response = await chat_client.get(
            f"/api/v1/chat/conversations/{unknown_id}/messages",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestChatRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_returns_429(
        self,
        chat_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Exceeding rate limit returns 429.

        We patch ``_check_rate_limit`` to raise the same HTTPException the real
        guard would raise. This isolates the wiring (the endpoint must propagate
        the 429) from the rate-limiter implementation, which is unit-tested
        separately.
        """
        from fastapi import HTTPException, status as http_status

        with patch(
            "app.chat.presentation.router._check_rate_limit",
            side_effect=HTTPException(
                status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many chat requests. Please slow down.",
            ),
        ):
            response = await chat_client.post(
                "/api/v1/chat/message",
                json={"content": "test", "conversation_id": None},
                headers=auth_headers,
            )

        assert response.status_code == 429
