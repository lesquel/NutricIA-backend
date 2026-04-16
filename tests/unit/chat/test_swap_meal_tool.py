"""Unit tests for the swap_planned_meal tool integration in SendMessageUseCase.

Tests that:
- When the LLM emits a tool_invoked event for swap_planned_meal,
  SendMessageUseCase calls SwapMealUseCase and yields tool_result.
- Ownership / plan-not-found errors yield tool_error.
- When swap_meal_use_case is None (not wired), tool invocations are silently ignored.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.chat.application.send_message_use_case import SendMessageUseCase
from app.chat.domain.entities import Conversation, ConversationContext, Message
from app.meal_plans.domain.errors import PlanNotFoundError


# ── Helpers ───────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_conversation(user_id: uuid.UUID) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title="test",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )


def _make_context(user_id: uuid.UUID) -> ConversationContext:
    return ConversationContext(
        user_id=user_id,
        recent_meals=[],
        retrieved_recipes=[],
        user_food_profile=None,
    )


@dataclass
class _FakeMacros:
    protein_g: float = 20.0
    carbs_g: float = 30.0
    fat_g: float = 8.0


@dataclass
class _FakePlannedMeal:
    id: uuid.UUID
    plan_id: uuid.UUID
    day_of_week: int
    meal_type: str
    recipe_name: str = "Arroz con pollo"
    recipe_ingredients: Any = None
    calories: float = 450.0
    macros: Any = None
    cook_time_minutes: int = 30
    difficulty: str = "easy"
    servings: int = 2
    is_logged: bool = False
    logged_meal_id: None = None

    def __post_init__(self) -> None:
        if self.recipe_ingredients is None:
            self.recipe_ingredients = ["arroz", "pollo"]
        if self.macros is None:
            self.macros = _FakeMacros()


@dataclass
class _FakePlan:
    id: uuid.UUID
    user_id: uuid.UUID
    meals: list[_FakePlannedMeal]


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def plan_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def meal_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_conv_repo(user_id: uuid.UUID) -> AsyncMock:
    repo = AsyncMock()
    conversation = _make_conversation(user_id)
    repo.create.return_value = conversation
    repo.get.return_value = conversation
    repo.update.return_value = conversation
    return repo


@pytest.fixture
def mock_msg_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.append.return_value = None
    repo.list_for_conversation.return_value = []
    return repo


@pytest.fixture
def mock_retriever(user_id: uuid.UUID) -> AsyncMock:
    retriever = AsyncMock()
    retriever.retrieve_context.return_value = _make_context(user_id)
    return retriever


def _make_llm_service_with_events(
    events: list[dict[str, Any]],
) -> MagicMock:
    """Return a mock ChatLLMService that yields the given events."""

    async def _stream(*args: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        for event in events:
            yield event
        yield {
            "type": "done",
            "message_id": str(uuid.uuid4()),
            "full_content": "",
            "recipe_cards": [],
        }

    llm = MagicMock()
    llm.astream_response = _stream
    return llm


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSendMessageUseCaseSwapMealTool:
    @pytest.mark.asyncio
    async def test_swap_tool_calls_swap_use_case(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        meal_id: uuid.UUID,
        mock_conv_repo: AsyncMock,
        mock_msg_repo: AsyncMock,
        mock_retriever: AsyncMock,
    ) -> None:
        """When LLM emits tool_invoked for swap_planned_meal, SwapMealUseCase is called."""
        planned_meal = _FakePlannedMeal(
            id=meal_id, plan_id=plan_id, day_of_week=1, meal_type="lunch"
        )
        fake_plan = _FakePlan(id=plan_id, user_id=user_id, meals=[planned_meal])

        swap_use_case = AsyncMock()
        swap_use_case._repo = AsyncMock()
        swap_use_case._repo.get.return_value = fake_plan
        swap_use_case.execute.return_value = planned_meal

        tool_args = {
            "plan_id": str(plan_id),
            "day_of_week": 1,
            "meal_type": "lunch",
            "constraints_text": "vegetarian",
        }
        llm_service = _make_llm_service_with_events(
            [{"type": "tool_invoked", "tool": "swap_planned_meal", "args": tool_args}]
        )

        use_case = SendMessageUseCase(
            conversation_repo=mock_conv_repo,
            message_repo=mock_msg_repo,
            retriever=mock_retriever,
            llm_service=llm_service,
            swap_meal_use_case=swap_use_case,
        )

        collected: list[dict[str, Any]] = []
        async for event in use_case.execute(user_id, None, "Cambia mi almuerzo"):
            collected.append(event)

        # SwapMealUseCase.execute was called
        swap_use_case.execute.assert_called_once()
        call_kwargs = swap_use_case.execute.call_args.kwargs
        assert call_kwargs["user_id"] == user_id
        assert call_kwargs["plan_id"] == plan_id
        assert call_kwargs["meal_id"] == meal_id

        # tool_result event was yielded
        tool_results = [e for e in collected if e.get("type") == "tool_result"]
        assert len(tool_results) == 1
        assert tool_results[0]["tool"] == "swap_planned_meal"

    @pytest.mark.asyncio
    async def test_plan_not_found_yields_tool_error(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        mock_conv_repo: AsyncMock,
        mock_msg_repo: AsyncMock,
        mock_retriever: AsyncMock,
    ) -> None:
        """PlanNotFoundError from SwapMealUseCase yields tool_error event."""
        swap_use_case = AsyncMock()
        swap_use_case._repo = AsyncMock()
        swap_use_case._repo.get.return_value = None  # Plan not found

        tool_args = {
            "plan_id": str(plan_id),
            "day_of_week": 0,
            "meal_type": "breakfast",
            "constraints_text": "",
        }
        llm_service = _make_llm_service_with_events(
            [{"type": "tool_invoked", "tool": "swap_planned_meal", "args": tool_args}]
        )

        use_case = SendMessageUseCase(
            conversation_repo=mock_conv_repo,
            message_repo=mock_msg_repo,
            retriever=mock_retriever,
            llm_service=llm_service,
            swap_meal_use_case=swap_use_case,
        )

        collected: list[dict[str, Any]] = []
        async for event in use_case.execute(user_id, None, "Cambia mi desayuno"):
            collected.append(event)

        tool_errors = [e for e in collected if e.get("type") == "tool_error"]
        assert len(tool_errors) == 1
        assert tool_errors[0]["tool"] == "swap_planned_meal"

    @pytest.mark.asyncio
    async def test_swap_use_case_none_ignores_tool_call(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        mock_conv_repo: AsyncMock,
        mock_msg_repo: AsyncMock,
        mock_retriever: AsyncMock,
    ) -> None:
        """When swap_meal_use_case is None, tool_invoked events are passed through unchanged."""
        tool_args = {
            "plan_id": str(plan_id),
            "day_of_week": 2,
            "meal_type": "dinner",
            "constraints_text": "gluten free",
        }
        llm_service = _make_llm_service_with_events(
            [{"type": "tool_invoked", "tool": "swap_planned_meal", "args": tool_args}]
        )

        use_case = SendMessageUseCase(
            conversation_repo=mock_conv_repo,
            message_repo=mock_msg_repo,
            retriever=mock_retriever,
            llm_service=llm_service,
            swap_meal_use_case=None,  # Not wired
        )

        collected: list[dict[str, Any]] = []
        async for event in use_case.execute(user_id, None, "Cambia mi cena"):
            collected.append(event)

        # tool_invoked is still yielded (for client awareness) but no tool_result/error
        tool_invoked = [e for e in collected if e.get("type") == "tool_invoked"]
        assert len(tool_invoked) == 1

        tool_results = [e for e in collected if e.get("type") == "tool_result"]
        tool_errors = [e for e in collected if e.get("type") == "tool_error"]
        assert len(tool_results) == 0
        assert len(tool_errors) == 0

    @pytest.mark.asyncio
    async def test_swap_use_case_execute_exception_yields_tool_error(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        meal_id: uuid.UUID,
        mock_conv_repo: AsyncMock,
        mock_msg_repo: AsyncMock,
        mock_retriever: AsyncMock,
    ) -> None:
        """Exception from SwapMealUseCase.execute yields tool_error."""
        planned_meal = _FakePlannedMeal(
            id=meal_id, plan_id=plan_id, day_of_week=3, meal_type="snack"
        )
        fake_plan = _FakePlan(id=plan_id, user_id=user_id, meals=[planned_meal])

        swap_use_case = AsyncMock()
        swap_use_case._repo = AsyncMock()
        swap_use_case._repo.get.return_value = fake_plan
        swap_use_case.execute.side_effect = PlanNotFoundError("Plan not owned by user")

        tool_args = {
            "plan_id": str(plan_id),
            "day_of_week": 3,
            "meal_type": "snack",
            "constraints_text": "low sugar",
        }
        llm_service = _make_llm_service_with_events(
            [{"type": "tool_invoked", "tool": "swap_planned_meal", "args": tool_args}]
        )

        use_case = SendMessageUseCase(
            conversation_repo=mock_conv_repo,
            message_repo=mock_msg_repo,
            retriever=mock_retriever,
            llm_service=llm_service,
            swap_meal_use_case=swap_use_case,
        )

        collected: list[dict[str, Any]] = []
        async for event in use_case.execute(user_id, None, "Cambia mi snack"):
            collected.append(event)

        tool_errors = [e for e in collected if e.get("type") == "tool_error"]
        assert len(tool_errors) == 1
        assert "Plan not owned by user" in tool_errors[0]["error"]
