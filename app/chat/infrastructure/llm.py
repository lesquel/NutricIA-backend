"""Chat infrastructure — LLM streaming service.

Uses LangChain's astream_events() for token streaming with multi-provider
fallback (mirrors the pattern from meals/infrastructure/ai_providers.py).

Supported providers: groq → gemini → openai → anthropic (fallback chain).

Tool-calling strategy:
    We use model.bind_tools([RecipeSuggestionTool, SwapPlannedMealTool]) so that
    LangChain emits structured tool_calls within the AIMessageChunk stream.
    We accumulate tool call argument strings across chunks, then on
    'on_chat_model_end' we inspect the final message for complete tool_calls.
    This is more reliable than on_tool_end (which only fires when LangChain
    executes the tool internally — not the case with bind_tools).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.chat.domain.entities import ConversationContext, Message
from app.chat.infrastructure.tools import RecipeSuggestionTool, SwapPlannedMealTool

logger = logging.getLogger("nutricia.chat.llm")

_SYSTEM_PROMPT_BASE = """You are NutricIA, an expert nutritional assistant.
You help users understand their eating habits, suggest healthy recipes, and provide personalized nutritional guidance.
Always be supportive, evidence-based, and culturally aware of Latin American / Ecuadorian cuisine.
When suggesting recipes, use the RecipeSuggestionTool tool to provide structured data.
"""

_CHAT_FALLBACK_PROVIDERS = ("groq", "gemini", "openai", "anthropic")


class ChatLLMService:
    """Streams LLM responses for chat messages.

    Yields ChatStreamEvent dicts:
        {"type": "token", "content": str}
        {"type": "recipe_card", "data": dict}
        {"type": "tool_invoked", "tool": str, "args": dict}
        {"type": "done", "message_id": str}
    """

    def _build_model(self) -> BaseChatModel:
        """Instantiate the primary chat model from settings."""
        from app.config import settings

        provider = settings.ai_provider
        model_name = settings.ai_model

        return _get_chat_model(provider, model_name or None)

    def _bind_tools(self, model: BaseChatModel) -> BaseChatModel:
        """Bind the tool schemas to the model for structured output.

        Groq's Llama tool-calling validator rejects payloads where the model
        stringifies nested objects/arrays/ints ("macros_per_serving" as a
        string, etc.), which aborts the whole stream mid-response. Llama 4
        Scout is especially prone to this. Skip tool binding for Groq so the
        model returns a plain text answer that reliably reaches the user —
        recipe cards become a nice-to-have instead of blocking the chat.
        """
        from app.config import settings

        if settings.ai_provider == "groq":
            return model

        return model.bind_tools(  # type: ignore[return-value]
            [RecipeSuggestionTool, SwapPlannedMealTool]
        )

    async def astream_response(
        self,
        system_prompt: str,
        history: list[Message],
        context: ConversationContext,
        query: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream response events.

        Parameters
        ----------
        system_prompt:
            Optional override for the system prompt.
        history:
            Recent conversation messages.
        context:
            RAG-retrieved context (meals, recipes, profile).
        query:
            The current user query.

        Yields
        ------
        dict events with "type" key:
            "token" | "recipe_card" | "tool_invoked" | "done"
        """
        base_model = self._build_model()
        model = self._bind_tools(base_model)

        # Build LangChain messages
        lc_messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt or _SYSTEM_PROMPT_BASE)
        ]

        # Inject context as a system-level JSON block
        context_block = json.dumps(
            {
                "recent_meals": context.recent_meals[:5],
                "relevant_foods": context.retrieved_recipes[:5],
                "user_food_profile": context.user_food_profile,
            },
            ensure_ascii=False,
            default=str,
        )
        lc_messages.append(
            SystemMessage(
                content=f"<nutritional_context>\n{context_block}\n</nutritional_context>"
            )
        )

        # Append conversation history
        for msg in history[-10:]:  # Last 10 messages max
            if msg.role == "user":
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                lc_messages.append(AIMessage(content=msg.content))

        # Current user query
        lc_messages.append(HumanMessage(content=query))

        accumulated_content: list[str] = []
        recipe_cards: list[dict[str, Any]] = []

        # Track tool call argument accumulation across chunks
        # tool_call_accum: {index -> {"name": str, "args_str": str, "id": str}}
        tool_call_accum: dict[int, dict[str, Any]] = {}

        try:
            async for event in model.astream_events(lc_messages, version="v2"):
                event_type: str = event.get("event", "")

                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk is not None:
                        # Yield text tokens
                        content = getattr(chunk, "content", "")
                        if content:
                            accumulated_content.append(content)
                            yield {"type": "token", "content": content}

                        # Accumulate tool call argument chunks
                        tool_calls = getattr(chunk, "tool_call_chunks", None) or []
                        for tc_chunk in tool_calls:
                            idx = tc_chunk.get("index", 0)
                            if idx not in tool_call_accum:
                                tool_call_accum[idx] = {
                                    "name": tc_chunk.get("name", ""),
                                    "args_str": "",
                                    "id": tc_chunk.get("id", ""),
                                }
                            if tc_chunk.get("name"):
                                tool_call_accum[idx]["name"] = tc_chunk["name"]
                            if tc_chunk.get("id"):
                                tool_call_accum[idx]["id"] = tc_chunk["id"]
                            tool_call_accum[idx]["args_str"] += tc_chunk.get("args", "")

                elif event_type == "on_chat_model_end":
                    # Process any completed tool calls from the final message
                    output = event.get("data", {}).get("output")
                    if output is not None:
                        tool_calls_final = getattr(output, "tool_calls", None) or []
                        for tc in tool_calls_final:
                            tool_name = tc.get("name", "")
                            tool_args = tc.get("args", {})
                            for tool_event in _process_tool_call(
                                tool_name, tool_args, recipe_cards
                            ):
                                yield tool_event

                # Legacy on_tool_end fallback (for providers that still use it)
                elif (
                    event_type == "on_tool_end"
                    and event.get("name") == "RecipeSuggestion"
                ):
                    legacy_output: Any = event.get("data", {}).get("output", {})
                    if isinstance(legacy_output, dict):
                        recipe_cards.append(legacy_output)
                        yield {"type": "recipe_card", "data": legacy_output}

        except Exception as exc:
            logger.error("LLM streaming error: %s", exc)
            # Yield partial content if any was accumulated
            if not accumulated_content:
                yield {
                    "type": "token",
                    "content": "Lo siento, ocurrió un error al procesar tu consulta.",
                }

        yield {
            "type": "done",
            "message_id": str(uuid.uuid4()),
            "full_content": "".join(accumulated_content),
            "recipe_cards": recipe_cards,
        }


def _process_tool_call(
    tool_name: str,
    tool_args: dict[str, Any],
    recipe_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert a completed tool call into stream events.

    Returns a list of events to yield (0 or 1 items).
    """
    if tool_name == "RecipeSuggestionTool":
        try:
            # Validate via Pydantic schema then convert to domain dataclass
            validated = RecipeSuggestionTool(**tool_args)
            recipe_data = validated.model_dump()
            recipe_cards.append(recipe_data)
            return [{"type": "recipe_card", "data": recipe_data}]
        except Exception as exc:
            logger.warning("Failed to parse RecipeSuggestionTool call: %s", exc)
            return []

    if tool_name == "SwapPlannedMealTool":
        return [
            {"type": "tool_invoked", "tool": "swap_planned_meal", "args": tool_args}
        ]

    return []


# ── Provider helpers (mirrors ai_providers.py pattern) ──────────────────────


def _get_chat_model(provider: str, model_override: str | None = None) -> BaseChatModel:
    """Instantiate a LangChain ChatModel for the given provider."""
    from app.config import settings

    if provider == "groq":
        from langchain_groq import ChatGroq
        from pydantic import SecretStr

        model = model_override or "meta-llama/llama-4-scout-17b-16e-instruct"
        return ChatGroq(  # type: ignore[call-arg]
            model=model,
            temperature=0.7,
            api_key=SecretStr(settings.groq_api_key)
            if settings.groq_api_key
            else None,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = model_override or "gemini-2.0-flash"
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0.7,
            google_api_key=settings.google_api_key or None,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        model = model_override or "gpt-4o"
        return ChatOpenAI(
            model=model,
            temperature=0.7,
            api_key=SecretStr(settings.openai_api_key)
            if settings.openai_api_key
            else None,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        from pydantic import SecretStr

        model = model_override or "claude-sonnet-4-20250514"
        api_key = (
            SecretStr(settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )
        if api_key:
            return ChatAnthropic(  # type: ignore[call-arg]
                model_name=model, temperature=0.7, api_key=api_key
            )
        return ChatAnthropic(model_name=model, temperature=0.7)  # type: ignore[call-arg]

    # Fallback: try groq (primary) then gemini
    logger.warning("Unknown provider '%s' for chat — falling back to groq", provider)
    return _get_chat_model("groq", model_override)
