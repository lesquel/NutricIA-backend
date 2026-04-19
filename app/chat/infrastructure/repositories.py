"""Chat infrastructure — repository implementations."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.domain.entities import Conversation, Message
from app.chat.infrastructure.models import ConversationModel, MessageModel


def _ensure_utc(dt: datetime | None) -> datetime:
    """Re-attach UTC tzinfo if the datetime is naive (SQLite quirk)."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ConversationRepositoryImpl:
    """Concrete conversation repository backed by SQLAlchemy.

    Parameters
    ----------
    session:
        Open AsyncSession (injected per request or test).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: ConversationModel) -> Conversation:
        return Conversation(
            id=model.id,
            user_id=model.user_id,
            title=model.title,
            created_at=_ensure_utc(model.created_at),
            updated_at=_ensure_utc(model.updated_at),
        )

    async def create(self, conversation: Conversation) -> Conversation:
        """Persist a new conversation."""
        model = ConversationModel(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get(self, id: uuid.UUID) -> Conversation | None:
        """Return the conversation with the given ID, or None."""
        stmt = select(ConversationModel).where(ConversationModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Conversation]:
        """Return conversations for a user, ordered by updated_at DESC."""
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, conversation: Conversation) -> Conversation:
        """Update an existing conversation."""
        stmt = select(ConversationModel).where(ConversationModel.id == conversation.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        model.title = conversation.title
        model.updated_at = conversation.updated_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)


class MessageRepositoryImpl:
    """Concrete message repository backed by SQLAlchemy.

    Parameters
    ----------
    session:
        Open AsyncSession (injected per request or test).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: MessageModel) -> Message:
        # metadata_ is now a native JSON column — SQLAlchemy returns the
        # parsed dict directly, no json.loads needed. Tolerate legacy rows
        # that may still contain a JSON-encoded string from the old
        # TEXT-backed schema.
        raw_metadata = model.metadata_
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata) if raw_metadata else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        elif isinstance(raw_metadata, dict):
            metadata = raw_metadata
        else:
            metadata = {}
        return Message(
            id=model.id,
            conversation_id=model.conversation_id,
            role=model.role,  # type: ignore[arg-type]
            content=model.content,
            metadata=metadata,
            created_at=_ensure_utc(model.created_at),
        )

    async def append(self, message: Message) -> Message:
        """Persist a new message."""
        model = MessageModel(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            metadata_=message.metadata or {},
            created_at=message.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def list_for_conversation(
        self,
        conversation_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Message]:
        """Return messages for a conversation, ordered by created_at ASC."""
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]
