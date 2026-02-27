"""AI food analysis providers — Strategy pattern for Gemini & OpenAI."""

import abc
import base64
import json
import logging

import httpx

from app.config import settings
from app.meals.schemas import ScanResult

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


class AIFoodAnalyzer(abc.ABC):
    """Abstract base for AI food analyzers."""

    @abc.abstractmethod
    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        ...


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
        result = json.loads(text)

        if "error" in result:
            raise FoodAnalysisError(result["error"])

        return ScanResult(**result)


class OpenAIAnalyzer(AIFoodAnalyzer):
    """OpenAI GPT-4o multimodal food analyzer."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_image}"

        payload = {
            "model": "gpt-4o",
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
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

        data = response.json()
        text = data["choices"][0]["message"]["content"]
        result = json.loads(text)

        if "error" in result:
            raise FoodAnalysisError(result["error"])

        return ScanResult(**result)


class FoodAnalysisError(Exception):
    """Raised when the AI detects a non-food or blurry image."""

    def __init__(self, error_type: str):
        self.error_type = error_type
        super().__init__(f"Food analysis failed: {error_type}")


def get_analyzer() -> AIFoodAnalyzer:
    """Factory: return the correct analyzer based on settings."""
    if settings.ai_provider == "openai":
        return OpenAIAnalyzer()
    return GeminiAnalyzer()
