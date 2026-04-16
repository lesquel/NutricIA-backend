"""Chat application — send message use case."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.chat.domain.entities import Conversation, Message
from app.chat.domain.errors import ConversationNotFoundError

if TYPE_CHECKING:
    from app.chat.domain.ports import (
        ConversationRepositoryPort,
        MessageRepositoryPort,
        RAGRetrieverPort,
    )
    from app.chat.infrastructure.llm import ChatLLMService

_HISTORY_LIMIT = 10
_TITLE_MAX_LEN = 50

logger = logging.getLogger("nutricia.chat.use_case")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SendMessageUseCase:
    """Orchestrates a single chat turn: retrieve context → stream LLM → persist.

    Parameters
    ----------
    conversation_repo:
        ConversationRepositoryPort implementation.
    message_repo:
        MessageRepositoryPort implementation.
    retriever:
        RAGRetrieverPort implementation.
    llm_service:
        ChatLLMService for streaming the model response.
    swap_meal_use_case:
        Optional SwapMealUseCase for handling swap_planned_meal tool calls.
        If None, tool_invoked events for swap_planned_meal are ignored.
    """

    def __init__(
        self,
        conversation_repo: "ConversationRepositoryPort",
        message_repo: "MessageRepositoryPort",
        retriever: "RAGRetrieverPort",
        llm_service: "ChatLLMService",
        swap_meal_use_case: Any = None,
    ) -> None:
        self._conv_repo = conversation_repo
        self._msg_repo = message_repo
        self._retriever = retriever
        self._llm = llm_service
        self._swap_meal_use_case = swap_meal_use_case

    async def execute(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        content: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute a chat turn as an async generator.

        Parameters
        ----------
        user_id:
            Authenticated user's ID.
        conversation_id:
            Existing conversation ID, or None to create a new one.
        content:
            The user's message text.

        Yields
        ------
        ChatStreamEvent dicts: {"type": "token"|"recipe_card"|"tool_invoked"|
                                         "tool_result"|"tool_error"|"done", ...}

        Raises
        ------
        ConversationNotFoundError:
            If conversation_id is given but not found or belongs to another user.
        """
        # Step 1: Resolve or create conversation
        if conversation_id is None:
            title = content[:_TITLE_MAX_LEN]
            conversation = await self._conv_repo.create(
                Conversation(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    title=title,
                    created_at=_utcnow(),
                    updated_at=_utcnow(),
                )
            )
        else:
            fetched = await self._conv_repo.get(conversation_id)
            if fetched is None or fetched.user_id != user_id:
                raise ConversationNotFoundError(
                    f"Conversation {conversation_id} not found for user {user_id}"
                )
            conversation = fetched

        # Step 2: Persist user message
        await self._msg_repo.append(
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role="user",
                content=content,
                metadata={},
                created_at=_utcnow(),
            )
        )

        # Step 3: Retrieve RAG context
        context = await self._retriever.retrieve_context(user_id, content)

        # Step 4: Fetch recent history
        history = await self._msg_repo.list_for_conversation(
            conversation.id,
            limit=_HISTORY_LIMIT,
            offset=0,
        )

        # Step 5: Stream LLM response
        accumulated: list[str] = []
        recipe_cards: list[dict[str, Any]] = []
        last_done: dict[str, Any] | None = None

        async for event in self._llm.astream_response(
            system_prompt="",
            history=history,
            context=context,
            query=content,
        ):
            if event["type"] == "token":
                accumulated.append(event.get("content", ""))
                yield event
            elif event["type"] == "recipe_card":
                recipe_cards.append(event.get("data", {}))
                yield event
            elif event["type"] == "tool_invoked":
                # Yield the invocation event so clients can show a loading state
                yield event
                # Intercept known tools and dispatch them
                tool_name = event.get("tool", "")
                tool_args = event.get("args", {})
                if tool_name == "swap_planned_meal":
                    async for tool_event in self._handle_swap_meal(user_id, tool_args):
                        yield tool_event
            elif event["type"] == "done":
                last_done = event
                yield event
            else:
                yield event

        # Step 6: Persist assistant message
        full_content = "".join(accumulated)
        if not full_content and last_done:
            full_content = last_done.get("full_content", "")

        await self._msg_repo.append(
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role="assistant",
                content=full_content or "(no response)",
                metadata={"recipe_cards": recipe_cards},
                created_at=_utcnow(),
            )
        )

        # Step 7: Update conversation updated_at
        updated_conv = Conversation(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=_utcnow(),
        )
        await self._conv_repo.update(updated_conv)

    async def _handle_swap_meal(
        self,
        user_id: uuid.UUID,
        tool_args: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Call SwapMealUseCase and yield tool_result or tool_error event."""
        if self._swap_meal_use_case is None:
            return

        try:
            import uuid as _uuid

            plan_id = _uuid.UUID(tool_args["plan_id"])
            day_of_week: int = int(tool_args["day_of_week"])
            meal_type: str = tool_args["meal_type"]
            constraints_text: str = tool_args.get("constraints_text", "")

            # Parse free-text constraints into DietaryConstraints (best-effort)
            constraints = _parse_constraints(constraints_text)

            # Find the meal matching day + type in the plan
            meal_id = await _resolve_meal_id(
                self._swap_meal_use_case,
                plan_id,
                day_of_week,
                meal_type,
            )
            if meal_id is None:
                yield {
                    "type": "tool_error",
                    "tool": "swap_planned_meal",
                    "error": f"No meal found for day={day_of_week}, type={meal_type} in plan {plan_id}",
                }
                return

            new_meal = await self._swap_meal_use_case.execute(
                user_id=user_id,
                plan_id=plan_id,
                meal_id=meal_id,
                swap_constraints=constraints,
                context={"constraints_text": constraints_text},
            )
            # Convert dataclass to dict for the event
            from dataclasses import asdict

            yield {
                "type": "tool_result",
                "tool": "swap_planned_meal",
                "result": asdict(new_meal),
            }
        except Exception as exc:
            logger.warning("swap_planned_meal tool failed: %s", exc)
            yield {
                "type": "tool_error",
                "tool": "swap_planned_meal",
                "error": str(exc),
            }


def _parse_constraints(text: str) -> "Any":
    """Best-effort parse of free-text constraints into DietaryConstraints."""
    from app.meal_plans.domain.entities import DietaryConstraints

    text_lower = text.lower()
    return DietaryConstraints(
        vegetarian="vegetarian" in text_lower or "vegetariano" in text_lower,
        vegan="vegan" in text_lower or "vegano" in text_lower,
        gluten_free="gluten" in text_lower,
        allergies=[],
    )


async def _resolve_meal_id(
    swap_use_case: Any,
    plan_id: "Any",
    day_of_week: int,
    meal_type: str,
) -> "Any":
    """Look up the meal ID in the plan for the given day+type."""
    plan = await swap_use_case._repo.get(plan_id)
    if plan is None:
        return None
    for meal in plan.meals:
        if meal.day_of_week == day_of_week and meal.meal_type == meal_type:
            return meal.id
    return None
