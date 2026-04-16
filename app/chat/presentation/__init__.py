"""Chat presentation — Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4096)
    conversation_id: uuid.UUID | None = None


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    updated_at: datetime


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MessagesListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationSummary]
    total: int


class ChatStreamEvent(BaseModel):
    type: Literal["token", "recipe_card", "done", "error"]
    content: str | None = None
    data: dict[str, Any] | None = None
    message_id: str | None = None
