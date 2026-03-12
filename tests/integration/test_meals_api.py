from datetime import datetime, timezone

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_meals_endpoint_returns_daily_summary(
    api_client: AsyncClient, auth_headers: dict
):
    create_response = await api_client.post(
        "/api/v1/meals",
        headers=auth_headers,
        json={
            "name": "Integration Breakfast",
            "calories": 420,
            "protein_g": 25,
            "carbs_g": 35,
            "fat_g": 16,
            "meal_type": "breakfast",
            "confidence_score": 0.92,
            "tags": ["integration", "protein"],
        },
    )
    assert create_response.status_code == 201

    response = await api_client.get("/api/v1/meals", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["meals"]) == 1
    assert payload["total_calories"] == 420
    assert payload["total_protein"] == 25
    assert payload["total_carbs"] == 35
    assert payload["total_fat"] == 16
    assert payload["meals"][0]["name"] == "Integration Breakfast"


@pytest.mark.asyncio
async def test_post_meals_endpoint_creates_meal(
    api_client: AsyncClient, auth_headers: dict
):
    logged_at = datetime.now(timezone.utc).isoformat()
    response = await api_client.post(
        "/api/v1/meals",
        headers=auth_headers,
        json={
            "name": "Integration Lunch",
            "calories": 610,
            "protein_g": 44,
            "carbs_g": 52,
            "fat_g": 21,
            "meal_type": "lunch",
            "confidence_score": 0.88,
            "tags": ["home", "balanced"],
            "image_url": "https://example.com/meal.jpg",
            "logged_at": logged_at,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Integration Lunch"
    assert payload["calories"] == 610
    assert payload["protein_g"] == 44
    assert payload["carbs_g"] == 52
    assert payload["fat_g"] == 21
    assert payload["meal_type"] == "lunch"
    assert payload["confidence_score"] == 0.88
    assert set(payload["tags"]) == {"home", "balanced"}
