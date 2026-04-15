import pytest

from app.meals.domain import AIProviderError
from app.meals.infrastructure import ai_providers
from app.meals.presentation import ScanResult


@pytest.mark.asyncio
async def test_analyze_food_falls_back_when_primary_provider_is_quota_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    async def fake_invoke_provider(
        provider: str,
        message: object,
        model_override: str | None = None,
    ) -> ScanResult:
        attempts.append(provider)
        if provider == "gemini":
            raise AIProviderError(
                status_code=429,
                detail="quota exceeded",
                provider=provider,
                fallback_eligible=True,
            )

        return ScanResult(
            name="Fallback Meal",
            ingredients=["Rice", "Chicken"],
            calories=610,
            protein_g=34,
            carbs_g=52,
            fat_g=21,
            confidence=0.84,
            tags=["Fallback"],
        )

    monkeypatch.setattr(ai_providers.settings, "ai_provider", "gemini")
    monkeypatch.setattr(ai_providers.settings, "ai_model", "")
    monkeypatch.setattr(ai_providers.settings, "groq_api_key", "test-groq-key")
    monkeypatch.setattr(ai_providers.settings, "openai_api_key", "")
    monkeypatch.setattr(ai_providers.settings, "anthropic_api_key", "")
    monkeypatch.setattr(ai_providers.settings, "mistral_api_key", "")
    monkeypatch.setattr(ai_providers, "_invoke_provider", fake_invoke_provider)

    result = await ai_providers.analyze_food(b"fake-image" * 500, "image/jpeg")

    assert result.name == "Fallback Meal"
    assert attempts == ["gemini", "groq"]


@pytest.mark.asyncio
async def test_analyze_food_raises_quota_error_when_no_fallback_provider_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_invoke_provider(
        provider: str,
        message: object,
        model_override: str | None = None,
    ) -> ScanResult:
        raise AIProviderError(
            status_code=429,
            detail="quota exceeded",
            provider=provider,
            fallback_eligible=True,
        )

    monkeypatch.setattr(ai_providers.settings, "ai_provider", "gemini")
    monkeypatch.setattr(ai_providers.settings, "ai_model", "")
    monkeypatch.setattr(ai_providers.settings, "groq_api_key", "")
    monkeypatch.setattr(ai_providers.settings, "openai_api_key", "")
    monkeypatch.setattr(ai_providers.settings, "anthropic_api_key", "")
    monkeypatch.setattr(ai_providers.settings, "mistral_api_key", "")
    monkeypatch.setattr(ai_providers, "_invoke_provider", fake_invoke_provider)

    with pytest.raises(AIProviderError) as exc_info:
        await ai_providers.analyze_food(b"fake-image" * 500, "image/jpeg")

    assert exc_info.value.status_code == 429
    assert exc_info.value.provider == "gemini"


def test_classify_provider_exception_maps_quota_errors_to_429() -> None:
    error = ai_providers._classify_provider_exception(
        "gemini",
        RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded for model gemini-2.0-flash"),
    )

    assert error.status_code == 429
    assert error.fallback_eligible is True
    assert error.provider == "gemini"


@pytest.mark.asyncio
async def test_analyze_food_retries_provider_default_when_model_is_decommissioned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[tuple[str, str | None]] = []

    async def fake_invoke_provider(
        provider: str,
        message: object,
        model_override: str | None = None,
    ) -> ScanResult:
        attempts.append((provider, model_override))
        if model_override is None:
            raise AIProviderError(
                status_code=502,
                detail="configured model rejected",
                provider=provider,
                fallback_eligible=True,
                retry_with_default_model=True,
            )

        return ScanResult(
            name="Groq Default Meal",
            ingredients=["Rice"],
            calories=320,
            protein_g=8,
            carbs_g=61,
            fat_g=3,
            confidence=0.77,
            tags=["Recovered"],
        )

    monkeypatch.setattr(ai_providers.settings, "ai_provider", "groq")
    monkeypatch.setattr(ai_providers.settings, "ai_model", "llama-3.2-11b-vision-preview")
    monkeypatch.setattr(ai_providers.settings, "groq_api_key", "test-groq-key")
    monkeypatch.setattr(ai_providers, "_invoke_provider", fake_invoke_provider)

    result = await ai_providers.analyze_food(b"fake-image" * 500, "image/jpeg")

    assert result.name == "Groq Default Meal"
    assert attempts == [
        ("groq", None),
        ("groq", "meta-llama/llama-4-scout-17b-16e-instruct"),
    ]