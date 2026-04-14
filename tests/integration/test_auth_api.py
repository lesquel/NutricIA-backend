from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_endpoint_returns_token_and_user(api_client: AsyncClient):
    response = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "integration-register@example.com",
            "password": "securepass123",
            "name": "Integration Register",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert isinstance(payload.get("access_token"), str)
    assert isinstance(payload.get("refresh_token"), str)
    assert payload.get("token_type") == "bearer"
    assert payload["user"]["email"] == "integration-register@example.com"
    assert payload["user"]["name"] == "Integration Register"


@pytest.mark.asyncio
async def test_login_endpoint_returns_token_for_existing_user(api_client: AsyncClient):
    register_payload = {
        "email": "integration-login@example.com",
        "password": "securepass123",
        "name": "Integration Login",
    }
    register_response = await api_client.post(
        "/api/v1/auth/register", json=register_payload
    )
    assert register_response.status_code == 201

    response = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": "integration-login@example.com",
            "password": "securepass123",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("access_token"), str)
    assert isinstance(payload.get("refresh_token"), str)
    assert payload["user"]["email"] == "integration-login@example.com"


@pytest.mark.asyncio
async def test_me_endpoint_returns_authenticated_user(
    api_client: AsyncClient, auth_headers: dict
):
    response = await api_client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "test@example.com"
    assert payload["name"] == "Test User"
    assert payload["id"]


# ── OAuth endpoint ───────────────────────────


@pytest.mark.asyncio
async def test_oauth_google_with_valid_token_returns_200(api_client: AsyncClient):
    """POST /oauth with {provider, token} and mocked Google verify → 200."""
    fake_user_info = {
        "email": "oauth@example.com",
        "name": "OAuth User",
        "avatar_url": "https://example.com/avatar.png",
        "provider_id": "google-123",
    }

    with patch(
        "app.auth.application.oauth_login.verify_google_token",
        new_callable=AsyncMock,
        return_value=fake_user_info,
    ):
        response = await api_client.post(
            "/api/v1/auth/oauth",
            json={"provider": "google", "token": "mock-google-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("access_token"), str)
    assert isinstance(payload.get("refresh_token"), str)
    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == "oauth@example.com"
    assert payload["user"]["name"] == "OAuth User"


@pytest.mark.asyncio
async def test_oauth_without_token_returns_422(api_client: AsyncClient):
    """POST /oauth without token field → 422 validation error."""
    response = await api_client.post(
        "/api/v1/auth/oauth",
        json={"provider": "google"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_oauth_with_invalid_token_returns_401(api_client: AsyncClient):
    """POST /oauth with invalid token → 401."""
    from app.auth.domain import InvalidTokenError

    with patch(
        "app.auth.application.oauth_login.verify_google_token",
        new_callable=AsyncMock,
        side_effect=InvalidTokenError("Invalid Google token"),
    ):
        response = await api_client.post(
            "/api/v1/auth/oauth",
            json={"provider": "google", "token": "bad-token"},
        )

    assert response.status_code == 401
