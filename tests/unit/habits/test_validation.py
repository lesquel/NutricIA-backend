"""Tests for habit_id UUID path param validation."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestHabitIdUuidValidation:
    """habit_id path params must be valid UUIDs; non-UUIDs → 422."""

    @pytest.mark.asyncio
    async def test_valid_uuid_is_accepted(
        self, api_client: AsyncClient, auth_headers: dict
    ) -> None:
        """Valid UUID returns 404 (habit doesn't exist) — NOT 422."""
        valid_uuid = str(uuid.uuid4())
        resp = await api_client.post(
            f"/api/v1/habits/{valid_uuid}/check-in", headers=auth_headers
        )
        # 404 means the UUID was parsed correctly but habit not found
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_non_uuid_string_returns_422(
        self, api_client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await api_client.post(
            "/api/v1/habits/abc/check-in", headers=auth_headers
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_integer_string_returns_422(
        self, api_client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await api_client.post(
            "/api/v1/habits/123/check-in", headers=auth_headers
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_non_uuid_returns_422(
        self, api_client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await api_client.delete(
            "/api/v1/habits/not-a-uuid", headers=auth_headers
        )
        assert resp.status_code == 422
