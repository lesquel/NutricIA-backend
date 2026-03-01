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
from pydantic import ValidationError

from app.config import settings
from app.meals.domain import FoodAnalysisError, AIProviderError
from app.meals.presentation import ScanResult

logger = logging.getLogger(__name__)

REQUIRED_SCAN_FIELDS = {"name", "calories", "protein_g", "carbs_g", "fat_g", "confidence"}

ANALYSIS_PROMPT = """You are a precise nutritional analysis AI. Analyze this food photo.

Return ONLY valid JSON with this exact schema (no markdown, no extra text):
{
    "reasoning": "step-by-step breakdown of visible ingredients, portion sizes, and their individual estimated macros",
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
- Pay special attention to Latin American and Ecuadorian regional ingredients (e.g., mote, plátano maduro, tostado, fritada).
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


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extract the first valid JSON object from a possibly noisy model response."""
    text = raw_text.strip()

    # Fast path
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Markdown fences
    if text.startswith("```"):
        inner = text.split("\n", 1)[1] if "\n" in text else text[3:]
        inner = inner[:-3] if inner.endswith("```") else inner
        try:
            parsed = json.loads(inner.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Scan for first decodable JSON object in the text
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[idx:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise AIProviderError(
        status_code=502,
        detail="La IA devolvió una respuesta inválida (no JSON). Intenta de nuevo o cambia de modelo.",
    )


def _normalize_scan_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize common key variants from different models to ScanResult schema."""
    normalized = dict(payload)

    aliases = {
        "food_name": "name",
        "estimated_calories": "calories",
        "kcal": "calories",
        "protein": "protein_g",
        "proteins": "protein_g",
        "carbs": "carbs_g",
        "carbohydrates": "carbs_g",
        "fat": "fat_g",
        "fats": "fat_g",
    }

    for src, dst in aliases.items():
        if dst not in normalized and src in normalized:
            normalized[dst] = normalized[src]

    if "ingredients" not in normalized:
        normalized["ingredients"] = []
    elif isinstance(normalized["ingredients"], str):
        normalized["ingredients"] = [item.strip() for item in normalized["ingredients"].split(",") if item.strip()]

    if "tags" not in normalized:
        normalized["tags"] = []
    elif isinstance(normalized["tags"], str):
        normalized["tags"] = [item.strip() for item in normalized["tags"].split(",") if item.strip()]

    if "confidence" not in normalized:
        normalized["confidence"] = 0.7

    missing = sorted(field for field in REQUIRED_SCAN_FIELDS if field not in normalized)
    if missing:
        missing_text = ", ".join(missing)
        raise AIProviderError(
            status_code=422,
            detail=f"La IA respondió en un formato incompleto. Faltan campos: {missing_text}. Intenta de nuevo o cambia de modelo.",
        )

    return normalized


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
    result = _extract_json_object(text)

    if "error" in result:
        raise FoodAnalysisError(result["error"])

    normalized = _normalize_scan_result(result)
    try:
        return ScanResult(**normalized)
    except ValidationError as exc:
        missing_fields = [".".join(str(part) for part in err["loc"]) for err in exc.errors() if err.get("type") == "missing"]
        missing_text = ", ".join(missing_fields) if missing_fields else "campos requeridos"
        raise AIProviderError(
            status_code=422,
            detail=f"La IA devolvió datos inválidos para nutrición ({missing_text}). Intenta de nuevo o cambia de modelo.",
        ) from exc


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
