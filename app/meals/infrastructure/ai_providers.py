"""Meals infrastructure — AI food analysis providers (Strategy pattern)."""

import abc
import base64
import json
import logging

import httpx

from app.config import settings
from app.meals.domain import FoodAnalysisError
from app.meals.presentation.schemas import ScanResult

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


# ── Helpers ───────────────────────────────────


def _parse_result(text: str) -> ScanResult:
    """Parse JSON text into a ScanResult, raising FoodAnalysisError on known errors."""
    result = json.loads(text)
    if "error" in result:
        raise FoodAnalysisError(result["error"])
    return ScanResult(**result)


def _openai_compatible_payload(
    model: str,
    b64_image: str,
    mime_type: str,
    *,
    json_mode: bool = True,
) -> dict:
    """Build an OpenAI-compatible chat/completions payload with a vision message."""
    data_url = f"data:{mime_type};base64,{b64_image}"
    payload: dict = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": "low"},
                    },
                ],
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


async def _call_openai_compatible(
    url: str,
    api_key: str,
    payload: dict,
) -> str:
    """POST to an OpenAI-compatible endpoint and return the assistant text."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


# ── Abstract Base ─────────────────────────────


class AIFoodAnalyzer(abc.ABC):
    """Abstract base for AI food analyzers."""

    @abc.abstractmethod
    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        ...


# ── Google Gemini ─────────────────────────────


class GeminiAnalyzer(AIFoodAnalyzer):
    """Google Gemini multimodal food analyzer."""

    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": ANALYSIS_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.API_URL}?key={settings.gemini_api_key}",
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_result(text)


# ── OpenAI ────────────────────────────────────


class OpenAIAnalyzer(AIFoodAnalyzer):
    """OpenAI GPT-4o multimodal food analyzer."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = _openai_compatible_payload("gpt-4o", b64_image, mime_type)
        text = await _call_openai_compatible(self.API_URL, settings.openai_api_key, payload)
        return _parse_result(text)


# ── Anthropic Claude ──────────────────────────


class ClaudeAnalyzer(AIFoodAnalyzer):
    """Anthropic Claude (claude-sonnet-4-20250514) multimodal food analyzer."""

    API_URL = "https://api.anthropic.com/v1/messages"

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": ANALYSIS_PROMPT},
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.API_URL,
                json=payload,
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
            response.raise_for_status()

        data = response.json()
        text = data["content"][0]["text"]
        return _parse_result(text)


# ── DeepSeek ──────────────────────────────────


class DeepSeekAnalyzer(AIFoodAnalyzer):
    """DeepSeek (OpenAI-compatible) food analyzer."""

    API_URL = "https://api.deepseek.com/chat/completions"

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = _openai_compatible_payload("deepseek-chat", b64_image, mime_type)
        text = await _call_openai_compatible(self.API_URL, settings.deepseek_api_key, payload)
        return _parse_result(text)


# ── Groq ──────────────────────────────────────


class GroqAnalyzer(AIFoodAnalyzer):
    """Groq (OpenAI-compatible) multimodal food analyzer."""

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = _openai_compatible_payload("llama-4-scout-17b-16e-instruct", b64_image, mime_type)
        text = await _call_openai_compatible(self.API_URL, settings.groq_api_key, payload)
        return _parse_result(text)


# ── Mistral ───────────────────────────────────


class MistralAnalyzer(AIFoodAnalyzer):
    """Mistral (pixtral-large) multimodal food analyzer."""

    API_URL = "https://api.mistral.ai/v1/chat/completions"

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = _openai_compatible_payload("pixtral-large-latest", b64_image, mime_type)
        text = await _call_openai_compatible(self.API_URL, settings.mistral_api_key, payload)
        return _parse_result(text)


# ── Factory ───────────────────────────────────

_ANALYZERS: dict[str, type[AIFoodAnalyzer]] = {
    "gemini": GeminiAnalyzer,
    "openai": OpenAIAnalyzer,
    "anthropic": ClaudeAnalyzer,
    "deepseek": DeepSeekAnalyzer,
    "groq": GroqAnalyzer,
    "mistral": MistralAnalyzer,
}


def get_analyzer() -> AIFoodAnalyzer:
    """Factory: return the correct analyzer based on settings."""
    cls = _ANALYZERS.get(settings.ai_provider)
    if cls is None:
        raise ValueError(
            f"Unknown AI provider '{settings.ai_provider}'. "
            f"Supported: {', '.join(_ANALYZERS)}"
        )
    return cls()
