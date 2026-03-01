"""Meals infrastructure — AI food analysis via LangChain multimodal models.

Uses LangChain's unified ChatModel abstraction so swapping providers is just
changing AI_PROVIDER + AI_MODEL in .env.  API keys are read automatically by
each LangChain integration from their standard env vars (GOOGLE_API_KEY,
OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY).
"""

import base64
import json
import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.config import settings
from app.meals.domain import FoodAnalysisError, AIProviderError
from app.meals.presentation import ScanResult

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are a precise nutritional analysis AI. Analyze this food photo.

Return ONLY valid JSON with this exact schema (no markdown, no extra text):
{
  "name": "dish name in English",
  "ingredients": ["ingredient1", "ingredient2"],
  "calories": <number>,
  "protein_g": <number>,
  "carbs_g": <number>,
  "fat_g": <number>,
  "confidence": <float between 0.0 and 1.0>,
  "tags": ["tag1", "tag2"]
}

Rules:
- Calories, protein, carbs, fat must be realistic estimates for a single serving.
- Tags should describe nutritional qualities (e.g. "High Fiber", "Whole Grain", "Omega-3", "Low Sugar").
- Confidence should reflect how clearly you can identify the food (1.0 = very clear, 0.5 = uncertain).
- If the image does NOT contain food, return: {"error": "not_food"}
- If the image is too blurry to identify, return: {"error": "blurry"}
"""


# ── Provider registry ────────────────────────


def _build_gemini(model: str, **kw: Any) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=0.1,
        max_output_tokens=1024,
        google_api_key=settings.google_api_key or None,
        **kw,
    )


def _build_openai(model: str, **kw: Any) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        temperature=0.1,
        max_tokens=1024,
        api_key=settings.openai_api_key or None,
        **kw,
    )


def _build_anthropic(model: str, **kw: Any) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        temperature=0.1,
        max_tokens=1024,
        api_key=settings.anthropic_api_key or None,
        **kw,
    )


def _build_deepseek(model: str, **kw: Any) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        temperature=0.1,
        max_tokens=1024,
        api_key=settings.deepseek_api_key or None,
        base_url="https://api.deepseek.com",
        **kw,
    )


def _build_groq(model: str, **kw: Any) -> BaseChatModel:
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model,
        temperature=0.1,
        max_tokens=1024,
        api_key=settings.groq_api_key or None,
        **kw,
    )


def _build_mistral(model: str, **kw: Any) -> BaseChatModel:
    from langchain_mistralai import ChatMistralAI

    return ChatMistralAI(
        model=model,
        temperature=0.1,
        max_tokens=1024,
        api_key=settings.mistral_api_key or None,
        **kw,
    )


_PROVIDERS: dict[str, tuple[callable, str]] = {
    #  provider  → (builder, default_model)
    "gemini":    (_build_gemini,    "gemini-2.0-flash"),
    "openai":    (_build_openai,    "gpt-4o"),
    "anthropic": (_build_anthropic, "claude-sonnet-4-20250514"),
    "deepseek":  (_build_deepseek,  "deepseek-chat"),
    "groq":      (_build_groq,      "llama-4-scout-17b-16e-instruct"),
    "mistral":   (_build_mistral,   "pixtral-large-latest"),
}


def _get_chat_model() -> BaseChatModel:
    """Instantiate the LangChain ChatModel for the configured provider + model."""
    provider = settings.ai_provider

    if provider == "mock":
        return None  # handled separately in analyze()

    entry = _PROVIDERS.get(provider)
    if entry is None:
        raise ValueError(
            f"Unknown AI provider '{provider}'. "
            f"Supported: {', '.join([*_PROVIDERS, 'mock'])}"
        )

    builder, default_model = entry
    model = settings.ai_model or default_model
    return builder(model)


# ── Public API ───────────────────────────────


async def analyze_food(image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
    """Analyze a food image with the configured LLM provider.

    Builds a LangChain multimodal message, invokes the model, parses the JSON
    response into a ScanResult.
    """
    # Mock path for local dev without API keys
    if settings.ai_provider == "mock":
        return _mock_analyze(image_bytes)

    llm = _get_chat_model()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    message = HumanMessage(
        content=[
            {"type": "text", "text": ANALYSIS_PROMPT},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
            },
        ],
    )

    try:
        response = await llm.ainvoke([message])
    except Exception as exc:
        logger.error("AI provider error: %s", exc)
        raise AIProviderError(
            status_code=502,
            detail=f"AI provider '{settings.ai_provider}' failed: {exc}",
        ) from exc

    text = response.content if isinstance(response.content, str) else str(response.content)

    # Strip markdown fences if the model wraps its output
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse AI response as JSON: %s", text[:300])
        raise AIProviderError(
            status_code=502,
            detail="AI returned invalid JSON. Try again or switch model.",
        ) from exc

    if "error" in result:
        raise FoodAnalysisError(result["error"])

    return ScanResult(**result)


# ── Mock (local dev) ─────────────────────────


def _mock_analyze(image_bytes: bytes) -> ScanResult:
    """Deterministic placeholder result for local dev without API keys."""
    if len(image_bytes) < 2_000:
        raise FoodAnalysisError("blurry")

    return ScanResult(
        name="Mixed Meal",
        ingredients=["Protein", "Carbohydrates", "Vegetables"],
        calories=520,
        protein_g=28,
        carbs_g=54,
        fat_g=18,
        confidence=0.62,
        tags=["Estimated", "Balanced", "Mock Analysis"],
    )
