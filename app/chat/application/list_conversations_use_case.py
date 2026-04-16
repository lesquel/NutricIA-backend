"""Chat application — list conversations use case."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.chat.domain.entities import Conversation

if TYPE_CHECKING:
    from app.chat.domain.ports import ConversationRepositoryPort


class ListConversationsUseCase:
    """Returns a paginated list of conversations for a user.

    Parameters
    ----------
    conversation_repo:
        ConversationRepositoryPort implementation.
    """

    def __init__(self, conversation_repo: "ConversationRepositoryPort") -> None:
        self._repo = conversation_repo

    async def execute(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        """Return conversations ordered by updated_at DESC."""
        return await self._repo.list_for_user(user_id, limit=limit, offset=offset)
