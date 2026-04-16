"""Tests for AI food scanning."""

import pytest

from app.meals.application import scan_food as scan_food_module
from app.meals.application.scan_food import scan_food
from app.meals.presentation import ScanResult
from app.meals.domain import FoodAnalysisError


@pytest.mark.asyncio
async def test_scan_food_returns_meal_data(monkeypatch: pytest.MonkeyPatch):
    """Test that scanning a valid food image returns meal data."""
    fake_image = b"fake_image_bytes" * 200

    async def fake_analyze_food(_: bytes, __: str, ___=None) -> ScanResult:
        return ScanResult(
            name="Mixed Meal",
            ingredients=["Protein", "Vegetables"],
            calories=520,
            protein_g=28,
            carbs_g=54,
            fat_g=18,
            confidence=0.62,
            tags=["Estimated"],
        )

    monkeypatch.setattr(scan_food_module, "analyze_food", fake_analyze_food)

    result = await scan_food(fake_image, "image/jpeg")

    assert isinstance(result, ScanResult)
    assert result.name is not None
    assert result.calories > 0
    assert result.confidence >= 0.0
    assert result.confidence <= 1.0


@pytest.mark.asyncio
async def test_scan_food_with_invalid_image(monkeypatch: pytest.MonkeyPatch):
    """Test scanning an invalid/blurry image raises FoodAnalysisError."""
    fake_small_image = b"tiny"

    async def fake_analyze_food(_: bytes, __: str, ___=None) -> ScanResult:
        raise FoodAnalysisError("blurry")

    monkeypatch.setattr(scan_food_module, "analyze_food", fake_analyze_food)

    with pytest.raises(FoodAnalysisError) as exc_info:
        await scan_food(fake_small_image, "image/jpeg")

    assert exc_info.value.error_type == "blurry"


@pytest.mark.asyncio
async def test_scan_food_calculates_confidence(monkeypatch: pytest.MonkeyPatch):
    """Test that confidence score is calculated and within valid range."""
    fake_image = b"valid_image_data" * 200

    async def fake_analyze_food(_: bytes, __: str, ___=None) -> ScanResult:
        return ScanResult(
            name="Oatmeal",
            ingredients=["Oats", "Milk", "Banana"],
            calories=340,
            protein_g=12,
            carbs_g=56,
            fat_g=8,
            confidence=0.83,
            tags=["Breakfast"],
        )

    monkeypatch.setattr(scan_food_module, "analyze_food", fake_analyze_food)

    result = await scan_food(fake_image, "image/jpeg")

    assert 0.0 <= result.confidence <= 1.0
