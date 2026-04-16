"""Chat presentation — FastAPI router.

Endpoints:
    POST /api/v1/chat/message     — SSE streaming chat response
    GET  /api/v1/chat/conversations — paginated list of conversations
    GET  /api/v1/chat/conversations/{id}/messages — message history
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.chat.application.list_conversations_use_case import ListConversationsUseCase
from app.chat.application.send_message_use_case import SendMessageUseCase
from app.chat.domain.errors import ConversationNotFoundError
from app.chat.infrastructure.llm import ChatLLMService
from app.chat.infrastructure.rag_retriever import CompositeRAGRetriever
from app.chat.infrastructure.repositories import (
    ConversationRepositoryImpl,
    MessageRepositoryImpl,
)
from app.chat.presentation import (
    ConversationsListResponse,
    ConversationSummary,
    MessageResponse,
    MessagesListResponse,
    SendMessageRequest,
)
from app.dependencies import DB, CurrentUser

# Optional: UserFoodProfileRepositoryImpl from learning_loop (iter 4A).
# Use try-import with fallback so this module still loads before 4A is merged.
try:
    from app.learning_loop.infrastructure.repositories import (
        UserFoodProfileRepositoryImpl,
    )

    _profile_repo_available = True
except ImportError:
    UserFoodProfileRepositoryImpl = None  # type: ignore[assignment,misc]
    _profile_repo_available = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# ── Rate limiter (in-memory, mirrors auth pattern) ────────────────────────────

_chat_rate_store: dict[str, float] = defaultdict(float)
_CHAT_RATE_WINDOW = 60  # 1 request per 60s per user (generous for dev; tighten in prod)
_CHAT_MAX_REQUESTS = 60  # 60 requests per window (per minute)

# Sliding window: store list of timestamps
_chat_requests: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(user_id: str) -> None:
    """Raise 429 if user exceeds 60 messages/minute."""
    now = time.monotonic()
    key = f"chat:{user_id}"
    timestamps = _chat_requests[key]
    # Remove timestamps outside the window
    _chat_requests[key] = [t for t in timestamps if now - t < _CHAT_RATE_WINDOW]
    if len(_chat_requests[key]) >= _CHAT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many chat requests. Please slow down.",
        )
    _chat_requests[key].append(now)


# ── Dependency factories ──────────────────────────────────────────────────────


def _get_embeddings_provider() -> Any:
    """Return the configured embeddings provider (or None for fire-and-forget)."""
    from app.config import settings
    from app.shared.infrastructure.embeddings import (
        DualEmbeddingsProvider,
        GeminiEmbeddingsProvider,
        OpenAIEmbeddingsProvider,
    )

    if settings.google_api_key and settings.openai_api_key:
        return DualEmbeddingsProvider(
            primary=GeminiEmbeddingsProvider(settings.google_api_key),
            fallback=OpenAIEmbeddingsProvider(settings.openai_api_key),
        )
    if settings.google_api_key:
        return GeminiEmbeddingsProvider(settings.google_api_key)
    if settings.openai_api_key:
        return OpenAIEmbeddingsProvider(settings.openai_api_key)
    return None


def _get_meal_vector_store() -> Any:
    """Return the meal embeddings vector store (env-driven)."""
    from app.shared.infrastructure.vector_store import get_vector_store

    return get_vector_store("meal_embeddings")


def _get_catalog_vector_store() -> Any:
    """Return the food catalog vector store (env-driven)."""
    from app.shared.infrastructure.vector_store import get_vector_store

    return get_vector_store("food_catalog")


def _get_user_food_profile_repo(db: Any) -> Any:
    """Return the UserFoodProfile repo if learning_loop is available, else stub."""
    if _profile_repo_available and UserFoodProfileRepositoryImpl is not None:
        return UserFoodProfileRepositoryImpl(db)

    # Stub — learning_loop not yet merged (iter 4A)
    class _StubRepo:
        async def get_for_user(self, user_id: uuid.UUID) -> None:
            return None

    return _StubRepo()


def _get_swap_meal_use_case(db: Any) -> Any:
    """Return SwapMealUseCase if meal_plans is wired, else None (graceful)."""
    try:
        from app.meal_plans.application.swap_meal_use_case import SwapMealUseCase
        from app.meal_plans.infrastructure.plan_generator import LLMPlanGenerator
        from app.meal_plans.infrastructure.repositories import MealPlanRepositoryImpl

        plan_repo = MealPlanRepositoryImpl(db)
        generator = LLMPlanGenerator()
        return SwapMealUseCase(plan_repo=plan_repo, generator=generator)
    except Exception:
        logger.warning(
            "SwapMealUseCase not available — swap_planned_meal tool disabled"
        )
        return None


# ── SSE helper ────────────────────────────────────────────────────────────────


async def _sse_generator(
    use_case: SendMessageUseCase,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    content: str,
) -> AsyncGenerator[str, None]:
    """Wrap the use case stream into SSE-formatted lines."""
    try:
        async for event in use_case.execute(user_id, conversation_id, content):
            data = json.dumps(event, ensure_ascii=False, default=str)
            yield f"data: {data}\n\n"
    except ConversationNotFoundError as exc:
        error_data = json.dumps({"type": "error", "detail": str(exc)})
        yield f"data: {error_data}\n\n"
    except Exception:
        logger.exception("Unexpected error in chat SSE stream")
        error_data = json.dumps({"type": "error", "detail": "Internal server error"})
        yield f"data: {error_data}\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/message")
async def send_message(
    body: SendMessageRequest,
    user: CurrentUser,
    db: DB,
) -> StreamingResponse:
    """Send a chat message and receive a streaming SSE response.

    Returns an EventSource stream with events:
    - `{"type": "token", "content": "..."}` — LLM text chunks
    - `{"type": "recipe_card", "data": {...}}` — structured recipe
    - `{"type": "done", "message_id": "..."}` — stream complete
    - `{"type": "error", "detail": "..."}` — on error
    """
    _check_rate_limit(str(user.id))

    embeddings = _get_embeddings_provider()
    meal_vs = _get_meal_vector_store()
    catalog_vs = _get_catalog_vector_store()
    profile_repo = _get_user_food_profile_repo(db)
    swap_use_case = _get_swap_meal_use_case(db)

    retriever = CompositeRAGRetriever(
        meal_vector_store=meal_vs,
        catalog_vector_store=catalog_vs,
        user_food_profile_repo=profile_repo,
        embeddings_provider=embeddings,
        db_session=db,
    )
    llm_service = ChatLLMService()
    conv_repo = ConversationRepositoryImpl(db)
    msg_repo = MessageRepositoryImpl(db)

    use_case = SendMessageUseCase(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        retriever=retriever,
        llm_service=llm_service,
        swap_meal_use_case=swap_use_case,
    )

    return StreamingResponse(
        _sse_generator(use_case, user.id, body.conversation_id, body.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=ConversationsListResponse)
async def list_conversations(
    user: CurrentUser,
    db: DB,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConversationsListResponse:
    """Return paginated list of conversations for the authenticated user."""
    conv_repo = ConversationRepositoryImpl(db)
    use_case = ListConversationsUseCase(conv_repo)
    conversations = await use_case.execute(user.id, limit=limit, offset=offset)

    return ConversationsListResponse(
        conversations=[
            ConversationSummary(
                id=c.id,
                title=c.title,
                updated_at=c.updated_at,
            )
            for c in conversations
        ],
        total=len(conversations),
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessagesListResponse,
)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> MessagesListResponse:
    """Return messages for a conversation, scoped to the authenticated user."""
    conv_repo = ConversationRepositoryImpl(db)
    msg_repo = MessageRepositoryImpl(db)

    # Validate conversation belongs to user
    conv = await conv_repo.get(conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    messages = await msg_repo.list_for_conversation(
        conversation_id, limit=limit, offset=offset
    )

    return MessagesListResponse(
        messages=[
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                metadata=m.metadata,
                created_at=m.created_at,
            )
            for m in messages
        ],
        total=len(messages),
    )
