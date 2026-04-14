"""Tests for water goal divide-by-zero guard."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import User


class TestWaterGoalDivideByZero:
    """When user.water_goal_ml is 0, no ZeroDivisionError should occur."""

    @pytest.mark.asyncio
    async def test_water_goal_zero_no_exception(
        self,
        api_client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Setting water_goal_ml=0 on user must not cause division error."""
        # Force user.water_goal_ml to 0 (bypassing validation — simulating DB state)
        test_user.water_goal_ml = 0
        await db_session.commit()

        resp = await api_client.get("/api/v1/habits/water", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["goal_cups"] >= 0

    @pytest.mark.asyncio
    async def test_water_post_goal_zero_no_exception(
        self,
        api_client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """POST water with water_goal_ml=0 must use safe fallback."""
        test_user.water_goal_ml = 0
        await db_session.commit()

        resp = await api_client.post(
            "/api/v1/habits/water",
            headers=auth_headers,
            json={"cups": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        # With the guard max(0, 1)=1, goal_cups = round(1/250) = 0
        # Without guard: round(0/250) = 0 — same result but less safe
        assert data["goal_cups"] >= 0
