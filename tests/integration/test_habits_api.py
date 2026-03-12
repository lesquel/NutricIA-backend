import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_habits_endpoint_returns_user_habits(
    api_client: AsyncClient, auth_headers: dict
):
    create_response = await api_client.post(
        "/api/v1/habits",
        headers=auth_headers,
        json={
            "name": "Integration Habit",
            "icon": "eco",
            "plant_type": "fern",
        },
    )
    assert create_response.status_code == 201

    response = await api_client.get("/api/v1/habits", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Integration Habit"
    assert payload[0]["icon"] == "eco"
    assert payload[0]["plant_type"] == "fern"


@pytest.mark.asyncio
async def test_post_habits_endpoint_creates_habit(
    api_client: AsyncClient, auth_headers: dict
):
    response = await api_client.post(
        "/api/v1/habits",
        headers=auth_headers,
        json={
            "name": "Daily Stretch",
            "icon": "self_improvement",
            "plant_type": "mint",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Daily Stretch"
    assert payload["icon"] == "self_improvement"
    assert payload["plant_type"] == "mint"
    assert payload["streak_days"] == 0
    assert payload["level"] == 0
