"""Chat domain errors."""

from __future__ import annotations


class ChatError(Exception):
    """Base error for the chat domain."""


class ConversationNotFoundError(ChatError):
    """Raised when a conversation cannot be found."""


class MessageValidationError(ChatError):
    """Raised when a message fails domain validation."""


class RAGRetrievalError(ChatError):
    """Raised when RAG context retrieval fails."""
