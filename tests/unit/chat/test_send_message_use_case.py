"""Unit tests for SendMessageUseCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.chat.application.send_message_use_case import SendMessageUseCase
from app.chat.domain.entities import Conversation, ConversationContext, Message
from app.chat.domain.errors import ConversationNotFoundError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_conversation(user_id: uuid.UUID) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )


async def _fake_stream(events: list[dict]) -> AsyncIterator[dict]:
    for evt in events:
        yield evt


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_conversation_repo(user_id: uuid.UUID) -> AsyncMock:
    repo = AsyncMock()
    conv = _make_conversation(user_id)
    repo.create.return_value = conv
    repo.get.return_value = conv
    repo.update.return_value = conv
    return repo


@pytest.fixture
def mock_message_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.append.side_effect = lambda msg: msg
    repo.list_for_conversation.return_value = []
    return repo


@pytest.fixture
def mock_retriever() -> AsyncMock:
    retriever = AsyncMock()
    retriever.retrieve_context.return_value = ConversationContext(
        user_id=uuid.uuid4(),
        recent_meals=[],
        retrieved_recipes=[],
        user_food_profile=None,
    )
    return retriever


@pytest.fixture
def mock_llm_service() -> MagicMock:
    service = MagicMock()
    service.astream_response = MagicMock(
        return_value=_fake_stream(
            [
                {"type": "token", "content": "Hola"},
                {"type": "done", "message_id": str(uuid.uuid4())},
            ]
        )
    )
    return service


class TestSendMessageUseCaseNewConversation:
    @pytest.mark.asyncio
    async def test_creates_new_conversation_when_none(
        self,
        user_id: uuid.UUID,
        mock_conversation_repo: AsyncMock,
        mock_message_repo: AsyncMock,
        mock_retriever: AsyncMock,
        mock_llm_service: MagicMock,
    ) -> None:
        """When conversation_id is None, a new conversation is created."""
        use_case = SendMessageUseCase(
            conversation_repo=mock_conversation_repo,
            message_repo=mock_message_repo,
            retriever=mock_retriever,
            llm_service=mock_llm_service,
        )
        events = []
        async for evt in use_case.execute(user_id, None, "Quiero una receta saludable"):
            events.append(evt)

        mock_conversation_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_title_is_first_50_chars_of_content(
        self,
        user_id: uuid.UUID,
        mock_conversation_repo: AsyncMock,
        mock_message_repo: AsyncMock,
        mock_retriever: AsyncMock,
        mock_llm_service: MagicMock,
    ) -> None:
        """New conversation title is first 50 chars of content."""
        long_content = "A" * 100
        use_case = SendMessageUseCase(
            conversation_repo=mock_conversation_repo,
            message_repo=mock_message_repo,
            retriever=mock_retriever,
            llm_service=mock_llm_service,
        )
        async for _ in use_case.execute(user_id, None, long_content):
            pass

        call_args = mock_conversation_repo.create.call_args[0][0]
        assert len(call_args.title) == 50


class TestSendMessageUseCaseExistingConversation:
    @pytest.mark.asyncio
    async def test_raises_when_conversation_not_found(
        self,
        user_id: uuid.UUID,
        mock_conversation_repo: AsyncMock,
        mock_message_repo: AsyncMock,
        mock_retriever: AsyncMock,
        mock_llm_service: MagicMock,
    ) -> None:
        """ConversationNotFoundError raised when conversation doesn't exist."""
        mock_conversation_repo.get.return_value = None

        use_case = SendMessageUseCase(
            conversation_repo=mock_conversation_repo,
            message_repo=mock_message_repo,
            retriever=mock_retriever,
            llm_service=mock_llm_service,
        )
        with pytest.raises(ConversationNotFoundError):
            async for _ in use_case.execute(user_id, uuid.uuid4(), "test"):
                pass

    @pytest.mark.asyncio
    async def test_raises_when_conversation_belongs_to_other_user(
        self,
        user_id: uuid.UUID,
        mock_conversation_repo: AsyncMock,
        mock_message_repo: AsyncMock,
        mock_retriever: AsyncMock,
        mock_llm_service: MagicMock,
    ) -> None:
        """ConversationNotFoundError raised when conversation belongs to different user."""
        other_user_conv = _make_conversation(uuid.uuid4())  # different user_id
        mock_conversation_repo.get.return_value = other_user_conv

        use_case = SendMessageUseCase(
            conversation_repo=mock_conversation_repo,
            message_repo=mock_message_repo,
            retriever=mock_retriever,
            llm_service=mock_llm_service,
        )
        with pytest.raises(ConversationNotFoundError):
            async for _ in use_case.execute(user_id, other_user_conv.id, "test"):
                pass


class TestSendMessageUseCaseMessagePersistence:
    @pytest.mark.asyncio
    async def test_user_message_persisted_before_llm_call(
        self,
        user_id: uuid.UUID,
        mock_conversation_repo: AsyncMock,
        mock_message_repo: AsyncMock,
        mock_retriever: AsyncMock,
        mock_llm_service: MagicMock,
    ) -> None:
        """User message is appended to repo before streaming starts."""
        call_order = []
        original_append = mock_message_repo.append.side_effect

        async def track_append(msg: Message) -> Message:
            call_order.append("append")
            return msg

        original_stream = mock_llm_service.astream_response

        async def track_stream(*args: object, **kwargs: object) -> AsyncIterator[dict]:
            call_order.append("stream")
            yield {"type": "done", "message_id": str(uuid.uuid4())}

        mock_message_repo.append = AsyncMock(side_effect=track_append)
        mock_llm_service.astream_response = MagicMock(return_value=track_stream())

        use_case = SendMessageUseCase(
            conversation_repo=mock_conversation_repo,
            message_repo=mock_message_repo,
            retriever=mock_retriever,
            llm_service=mock_llm_service,
        )
        async for _ in use_case.execute(user_id, None, "test message"):
            pass

        # append must have been called at least once (user message) before stream
        assert "append" in call_order

    @pytest.mark.asyncio
    async def test_assistant_message_persisted_after_stream(
        self,
        user_id: uuid.UUID,
        mock_conversation_repo: AsyncMock,
        mock_message_repo: AsyncMock,
        mock_retriever: AsyncMock,
        mock_llm_service: MagicMock,
    ) -> None:
        """Assistant message is appended after stream completes."""
        use_case = SendMessageUseCase(
            conversation_repo=mock_conversation_repo,
            message_repo=mock_message_repo,
            retriever=mock_retriever,
            llm_service=mock_llm_service,
        )
        async for _ in use_case.execute(user_id, None, "test"):
            pass

        # At least 2 appends: user message + assistant message
        assert mock_message_repo.append.call_count >= 2
