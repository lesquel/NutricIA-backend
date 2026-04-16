"""Chat domain public API."""

from app.chat.domain.entities import (
    Conversation,
    ConversationContext,
    Message,
    MessageRole,
    RecipeSuggestion,
)
from app.chat.domain.errors import (
    ChatError,
    ConversationNotFoundError,
    MessageValidationError,
    RAGRetrievalError,
)

__all__ = [
    "Conversation",
    "ConversationContext",
    "Message",
    "MessageRole",
    "RecipeSuggestion",
    "ChatError",
    "ConversationNotFoundError",
    "MessageValidationError",
    "RAGRetrievalError",
]
