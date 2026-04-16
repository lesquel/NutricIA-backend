"""Chat domain ports (Protocol interfaces)."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from app.chat.domain.entities import Conversation, ConversationContext, Message


@runtime_checkable
class ConversationRepositoryPort(Protocol):
    async def create(self, conversation: Conversation) -> Conversation: ...

    async def get(self, id: uuid.UUID) -> Conversation | None: ...

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Conversation]: ...

    async def update(self, conversation: Conversation) -> Conversation: ...


@runtime_checkable
class MessageRepositoryPort(Protocol):
    async def append(self, message: Message) -> Message: ...

    async def list_for_conversation(
        self,
        conversation_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Message]: ...


@runtime_checkable
class RAGRetrieverPort(Protocol):
    async def retrieve_context(
        self,
        user_id: uuid.UUID,
        query: str,
    ) -> ConversationContext: ...
