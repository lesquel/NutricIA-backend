"""Integration tests for POST /api/v1/auth/refresh endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_refresh_with_valid_token_returns_new_pair(api_client: AsyncClient):
    """POST /auth/refresh with a valid refresh token returns new access + refresh."""
    # Register to get a refresh token
    reg = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh-test@example.com",
            "password": "securepass123",
            "name": "Refresh Test",
        },
    )
    assert reg.status_code == 201
    refresh_token = reg.json()["refresh_token"]

    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["access_token"], str)
    assert isinstance(body["refresh_token"], str)
    # Old refresh token should be rotated (different from original)
    assert body["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_returns_401(api_client: AsyncClient):
    """POST /auth/refresh with bogus token → 401."""
    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-garbage-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_already_rotated_token_returns_401(api_client: AsyncClient):
    """POST /auth/refresh with an already-used token → 401 (rotation)."""
    reg = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh-rotate@example.com",
            "password": "securepass123",
            "name": "Rotate Test",
        },
    )
    assert reg.status_code == 201
    old_refresh = reg.json()["refresh_token"]

    # Use it once — should succeed and rotate
    first = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert first.status_code == 200

    # Use the OLD token again — should fail
    second = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert second.status_code == 401
