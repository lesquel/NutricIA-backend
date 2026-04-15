"""Meals domain — value objects and exceptions."""

from enum import StrEnum


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    SNACK = "snack"
    DINNER = "dinner"


class FoodAnalysisError(Exception):
    """Raised when the AI analysis cannot return a valid food result."""

    def __init__(self, error_type: str):
        self.error_type = error_type
        super().__init__(f"Food analysis failed: {error_type}")


class AIProviderError(Exception):
    """Raised when upstream AI provider request fails."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        provider: str | None = None,
        fallback_eligible: bool = False,
        retry_with_default_model: bool = False,
    ):
        self.status_code = status_code
        self.detail = detail
        self.provider = provider
        self.fallback_eligible = fallback_eligible
        self.retry_with_default_model = retry_with_default_model
        super().__init__(detail)
