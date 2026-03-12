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
