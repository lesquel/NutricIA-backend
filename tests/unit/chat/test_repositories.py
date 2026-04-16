"""Unit tests for chat infrastructure repositories."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.domain.entities import Conversation, Message
from app.chat.infrastructure.repositories import (
    ConversationRepositoryImpl,
    MessageRepositoryImpl,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_conversation(user_id: uuid.UUID | None = None) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        title="Test Conversation",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )


def _make_message(conversation_id: uuid.UUID) -> Message:
    return Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content="Hello, what should I eat today?",
        metadata={},
        created_at=_utcnow(),
    )


class TestConversationRepositoryImpl:
    @pytest.mark.asyncio
    async def test_create_and_get_round_trip(self, db_session: AsyncSession) -> None:
        """Creating a conversation and getting it by ID returns same data."""
        repo = ConversationRepositoryImpl(db_session)
        user_id = uuid.uuid4()
        conv = _make_conversation(user_id)

        created = await repo.create(conv)
        fetched = await repo.get(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.user_id == user_id
        assert fetched.title == "Test Conversation"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_id(
        self, db_session: AsyncSession
    ) -> None:
        """get() returns None when ID does not exist."""
        repo = ConversationRepositoryImpl(db_session)
        result = await repo.get(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_for_user_returns_user_conversations(
        self, db_session: AsyncSession
    ) -> None:
        """list_for_user returns only conversations belonging to that user."""
        repo = ConversationRepositoryImpl(db_session)
        user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        conv1 = _make_conversation(user_id)
        conv2 = _make_conversation(user_id)
        other_conv = _make_conversation(other_user_id)

        await repo.create(conv1)
        await repo.create(conv2)
        await repo.create(other_conv)

        results = await repo.list_for_user(user_id, limit=10, offset=0)
        assert len(results) == 2
        assert all(c.user_id == user_id for c in results)

    @pytest.mark.asyncio
    async def test_list_for_user_respects_limit_offset(
        self, db_session: AsyncSession
    ) -> None:
        """list_for_user pagination works correctly."""
        repo = ConversationRepositoryImpl(db_session)
        user_id = uuid.uuid4()

        for _ in range(5):
            await repo.create(_make_conversation(user_id))

        page1 = await repo.list_for_user(user_id, limit=3, offset=0)
        page2 = await repo.list_for_user(user_id, limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 2

    @pytest.mark.asyncio
    async def test_update_conversation(self, db_session: AsyncSession) -> None:
        """update() persists changes to the conversation."""
        repo = ConversationRepositoryImpl(db_session)
        conv = _make_conversation()
        created = await repo.create(conv)

        updated_conv = Conversation(
            id=created.id,
            user_id=created.user_id,
            title="Updated Title",
            created_at=created.created_at,
            updated_at=_utcnow(),
        )
        updated = await repo.update(updated_conv)
        assert updated.title == "Updated Title"

        fetched = await repo.get(created.id)
        assert fetched is not None
        assert fetched.title == "Updated Title"


class TestMessageRepositoryImpl:
    @pytest.mark.asyncio
    async def test_append_and_list(self, db_session: AsyncSession) -> None:
        """append() saves a message; list_for_conversation returns it."""
        conv_repo = ConversationRepositoryImpl(db_session)
        msg_repo = MessageRepositoryImpl(db_session)

        conv = await conv_repo.create(_make_conversation())
        msg = _make_message(conv.id)
        appended = await msg_repo.append(msg)

        messages = await msg_repo.list_for_conversation(conv.id, limit=10, offset=0)
        assert len(messages) == 1
        assert messages[0].id == appended.id
        assert messages[0].content == msg.content

    @pytest.mark.asyncio
    async def test_list_ordering_asc_by_created_at(
        self, db_session: AsyncSession
    ) -> None:
        """list_for_conversation returns messages ordered by created_at ASC."""
        import asyncio

        conv_repo = ConversationRepositoryImpl(db_session)
        msg_repo = MessageRepositoryImpl(db_session)

        conv = await conv_repo.create(_make_conversation())

        msg1 = Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="user",
            content="First message",
            metadata={},
            created_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        )
        msg2 = Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="assistant",
            content="Second message",
            metadata={},
            created_at=datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
        )
        await msg_repo.append(msg1)
        await msg_repo.append(msg2)

        messages = await msg_repo.list_for_conversation(conv.id, limit=10, offset=0)
        assert len(messages) == 2
        assert messages[0].content == "First message"
        assert messages[1].content == "Second message"

    @pytest.mark.asyncio
    async def test_messages_scoped_to_conversation(
        self, db_session: AsyncSession
    ) -> None:
        """Messages only returned for the specified conversation."""
        conv_repo = ConversationRepositoryImpl(db_session)
        msg_repo = MessageRepositoryImpl(db_session)

        conv1 = await conv_repo.create(_make_conversation())
        conv2 = await conv_repo.create(_make_conversation())

        await msg_repo.append(_make_message(conv1.id))
        await msg_repo.append(_make_message(conv2.id))

        msgs_conv1 = await msg_repo.list_for_conversation(conv1.id, limit=10, offset=0)
        msgs_conv2 = await msg_repo.list_for_conversation(conv2.id, limit=10, offset=0)

        assert len(msgs_conv1) == 1
        assert len(msgs_conv2) == 1
        assert msgs_conv1[0].conversation_id == conv1.id
        assert msgs_conv2[0].conversation_id == conv2.id
