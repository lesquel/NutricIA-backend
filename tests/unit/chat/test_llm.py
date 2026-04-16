"""Unit tests for ChatLLMService."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from unittest.mock import MagicMock, patch

import pytest

from app.chat.domain.entities import ConversationContext, Message
from app.chat.infrastructure.llm import ChatLLMService, _process_tool_call


def _make_context(user_id: uuid.UUID | None = None) -> ConversationContext:
    return ConversationContext(
        user_id=user_id or uuid.uuid4(),
        recent_meals=[{"name": "Arroz", "calories": 300}],
        retrieved_recipes=[],
        user_food_profile=None,
    )


def _make_history() -> list[Message]:
    return [
        Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role="user",
            content="Hola",
            metadata={},
            created_at=datetime.now(timezone.utc),
        )
    ]


async def _fake_astream_events(
    events: list[dict[str, Any]],
) -> AsyncIterator[dict[str, Any]]:
    for event in events:
        yield event


def _make_mock_model(events: list[dict[str, Any]]) -> MagicMock:
    """Build a mock LangChain model that streams the given events.

    bind_tools() returns the same mock so _bind_tools() is transparent.
    """
    mock_model = MagicMock()
    mock_model.astream_events = MagicMock(return_value=_fake_astream_events(events))
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    return mock_model


class TestChatLLMServiceTokenEvents:
    @pytest.mark.asyncio
    async def test_yields_token_events(self) -> None:
        """LLM token chunks are yielded as token events."""
        chunk1 = MagicMock(content="Hola ", type="AIMessageChunk", tool_call_chunks=[])
        chunk2 = MagicMock(content="mundo", type="AIMessageChunk", tool_call_chunks=[])

        fake_events = [
            {"event": "on_chat_model_stream", "data": {"chunk": chunk1}},
            {"event": "on_chat_model_stream", "data": {"chunk": chunk2}},
        ]

        mock_model = _make_mock_model(fake_events)

        with patch(
            "app.chat.infrastructure.llm.ChatLLMService._build_model",
            return_value=mock_model,
        ):
            service = ChatLLMService()
            events = []
            async for evt in service.astream_response(
                system_prompt="You are a nutrition assistant.",
                history=_make_history(),
                context=_make_context(),
                query="Dame una receta",
            ):
                events.append(evt)

        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) >= 1

    @pytest.mark.asyncio
    async def test_yields_done_event(self) -> None:
        """After streaming, a 'done' event is yielded."""
        mock_model = _make_mock_model([])

        with patch(
            "app.chat.infrastructure.llm.ChatLLMService._build_model",
            return_value=mock_model,
        ):
            service = ChatLLMService()
            events = []
            async for evt in service.astream_response(
                system_prompt="You are a nutrition assistant.",
                history=_make_history(),
                context=_make_context(),
                query="Dame una receta",
            ):
                events.append(evt)

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_bind_tools_is_called(self) -> None:
        """bind_tools is called on the model before streaming."""
        mock_model = _make_mock_model([])

        with patch(
            "app.chat.infrastructure.llm.ChatLLMService._build_model",
            return_value=mock_model,
        ):
            service = ChatLLMService()
            async for _ in service.astream_response(
                system_prompt="sys",
                history=[],
                context=_make_context(),
                query="test",
            ):
                pass

        mock_model.bind_tools.assert_called_once()
        bound_tools = mock_model.bind_tools.call_args[0][0]
        tool_names = [t.__name__ for t in bound_tools]
        assert "RecipeSuggestionTool" in tool_names
        assert "SwapPlannedMealTool" in tool_names


class TestChatLLMServiceToolCallParsing:
    @pytest.mark.asyncio
    async def test_tool_call_yields_recipe_card_event(self) -> None:
        """Legacy on_tool_end for RecipeSuggestion still yields a recipe_card event."""
        recipe_data = {
            "name": "Ensalada de quinua",
            "ingredients": ["quinua", "tomate", "pepino"],
            "macros_per_serving": {
                "calories": 320,
                "protein_g": 12,
                "carbs_g": 45,
                "fat_g": 8,
            },
            "cook_time_minutes": 20,
            "difficulty": "easy",
            "servings": 2,
            "steps": ["Cocinar quinua", "Mezclar ingredientes"],
        }

        fake_events = [
            {
                "event": "on_tool_end",
                "name": "RecipeSuggestion",
                "data": {"output": recipe_data},
            },
        ]

        mock_model = _make_mock_model(fake_events)

        with patch(
            "app.chat.infrastructure.llm.ChatLLMService._build_model",
            return_value=mock_model,
        ):
            service = ChatLLMService()
            events = []
            async for evt in service.astream_response(
                system_prompt="You are a nutrition assistant.",
                history=[],
                context=_make_context(),
                query="Recomiéndame una receta",
            ):
                events.append(evt)

        recipe_events = [e for e in events if e["type"] == "recipe_card"]
        assert len(recipe_events) == 1
        assert recipe_events[0]["data"]["name"] == "Ensalada de quinua"

    @pytest.mark.asyncio
    async def test_on_chat_model_end_tool_call_yields_recipe_card(self) -> None:
        """on_chat_model_end with RecipeSuggestionTool tool_call yields recipe_card."""
        recipe_args = {
            "name": "Sopa de lenteja",
            "ingredients": ["lenteja", "zanahoria"],
            "macros_per_serving": {
                "calories": 250.0,
                "protein_g": 15.0,
                "carbs_g": 35.0,
                "fat_g": 4.0,
            },
            "cook_time_minutes": 30,
            "difficulty": "easy",
            "servings": 2,
            "steps": ["Hervir lentejas", "Agregar zanahoria"],
        }

        final_message = MagicMock()
        final_message.tool_calls = [
            {"name": "RecipeSuggestionTool", "args": recipe_args, "id": "tc_001"},
        ]

        fake_events = [
            {
                "event": "on_chat_model_end",
                "data": {"output": final_message},
            },
        ]

        mock_model = _make_mock_model(fake_events)

        with patch(
            "app.chat.infrastructure.llm.ChatLLMService._build_model",
            return_value=mock_model,
        ):
            service = ChatLLMService()
            events = []
            async for evt in service.astream_response(
                system_prompt="",
                history=[],
                context=_make_context(),
                query="Receta de lenteja",
            ):
                events.append(evt)

        recipe_events = [e for e in events if e["type"] == "recipe_card"]
        assert len(recipe_events) == 1
        assert recipe_events[0]["data"]["name"] == "Sopa de lenteja"

    @pytest.mark.asyncio
    async def test_swap_planned_meal_tool_call_yields_tool_invoked(self) -> None:
        """on_chat_model_end with SwapPlannedMealTool yields tool_invoked event."""
        swap_args = {
            "plan_id": str(uuid.uuid4()),
            "day_of_week": 1,
            "meal_type": "lunch",
            "constraints_text": "vegetarian",
        }

        final_message = MagicMock()
        final_message.tool_calls = [
            {"name": "SwapPlannedMealTool", "args": swap_args, "id": "tc_002"},
        ]

        fake_events = [
            {
                "event": "on_chat_model_end",
                "data": {"output": final_message},
            },
        ]

        mock_model = _make_mock_model(fake_events)

        with patch(
            "app.chat.infrastructure.llm.ChatLLMService._build_model",
            return_value=mock_model,
        ):
            service = ChatLLMService()
            events = []
            async for evt in service.astream_response(
                system_prompt="",
                history=[],
                context=_make_context(),
                query="Cambia mi almuerzo del martes",
            ):
                events.append(evt)

        tool_invoked = [e for e in events if e["type"] == "tool_invoked"]
        assert len(tool_invoked) == 1
        assert tool_invoked[0]["tool"] == "swap_planned_meal"
        assert tool_invoked[0]["args"]["day_of_week"] == 1


class TestProcessToolCall:
    """Unit tests for the _process_tool_call helper."""

    def test_recipe_suggestion_tool_returns_recipe_card(self) -> None:
        """RecipeSuggestionTool args → recipe_card event."""
        args = {
            "name": "Ceviche",
            "ingredients": ["pescado", "limón", "cebolla"],
            "macros_per_serving": {
                "calories": 180.0,
                "protein_g": 25.0,
                "carbs_g": 8.0,
                "fat_g": 3.0,
            },
            "cook_time_minutes": 15,
            "difficulty": "easy",
            "servings": 1,
            "steps": ["Cortar pescado", "Marinar"],
        }
        cards: list[dict] = []
        result = _process_tool_call("RecipeSuggestionTool", args, cards)
        assert len(result) == 1
        assert result[0]["type"] == "recipe_card"
        assert result[0]["data"]["name"] == "Ceviche"
        assert len(cards) == 1

    def test_swap_planned_meal_tool_returns_tool_invoked(self) -> None:
        """SwapPlannedMealTool → tool_invoked event."""
        args = {
            "plan_id": str(uuid.uuid4()),
            "day_of_week": 0,
            "meal_type": "breakfast",
            "constraints_text": "low-carb",
        }
        cards: list[dict] = []
        result = _process_tool_call("SwapPlannedMealTool", args, cards)
        assert len(result) == 1
        assert result[0]["type"] == "tool_invoked"
        assert result[0]["tool"] == "swap_planned_meal"

    def test_unknown_tool_returns_empty(self) -> None:
        """Unknown tool name → empty list."""
        cards: list[dict] = []
        result = _process_tool_call("UnknownTool", {}, cards)
        assert result == []


class TestChatLLMServiceFallback:
    @pytest.mark.asyncio
    async def test_model_build_called(self) -> None:
        """_build_model is called during streaming."""
        mock_model = _make_mock_model([])

        with patch(
            "app.chat.infrastructure.llm.ChatLLMService._build_model",
            return_value=mock_model,
        ) as mock_build:
            service = ChatLLMService()
            async for _ in service.astream_response(
                system_prompt="sys",
                history=[],
                context=_make_context(),
                query="test",
            ):
                pass
            mock_build.assert_called_once()
