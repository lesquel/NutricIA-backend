"""Integration tests for POST /api/v1/auth/logout endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_logout_returns_204_and_blocks_token(api_client: AsyncClient):
    """POST /auth/logout revokes the access token and all refresh tokens."""
    reg = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout-test@example.com",
            "password": "securepass123",
            "name": "Logout Test",
        },
    )
    assert reg.status_code == 201
    access_token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Logout
    response = await api_client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 204

    # The same access token should now be blocked
    me_resp = await api_client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_tokens(api_client: AsyncClient):
    """After logout, previously issued refresh tokens should be invalid."""
    reg = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout-refresh@example.com",
            "password": "securepass123",
            "name": "Logout Refresh",
        },
    )
    assert reg.status_code == 201
    access_token = reg.json()["access_token"]
    refresh_token = reg.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Logout
    await api_client.post("/api/v1/auth/logout", headers=headers)

    # Refresh should fail
    refresh_resp = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_requires_authentication(api_client: AsyncClient):
    """POST /auth/logout without a valid token returns 401/403."""
    response = await api_client.post("/api/v1/auth/logout")
    assert response.status_code == 401
