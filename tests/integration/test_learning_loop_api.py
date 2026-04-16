"""Integration tests for learning_loop API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning_loop.domain.entities import UserFoodProfile
from app.learning_loop.infrastructure.repositories import (
    UserFoodProfileRepositoryImpl,
)


# ── GET /users/me/food-profile ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_food_profile_returns_404_when_not_built(
    api_client: AsyncClient,
    auth_headers: dict,
) -> None:
    response = await api_client.get(
        "/api/v1/users/me/food-profile",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_food_profile_returns_200_when_exists(
    api_client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session: AsyncSession,
) -> None:
    # Pre-populate a profile
    repo = UserFoodProfileRepositoryImpl(db_session)
    profile = UserFoodProfile(
        user_id=test_user.id,
        frequent_foods=[{"canonical_name": "Empanadas", "count": 5}],
        avoided_tags=[],
        avg_daily_macros={"protein_g": 80.0, "carbs_g": 200.0, "fat_g": 50.0},
        updated_at=datetime.now(timezone.utc),
    )
    await repo.upsert(profile)
    await db_session.commit()

    response = await api_client.get(
        "/api/v1/users/me/food-profile",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(test_user.id)
    assert len(data["frequent_foods"]) == 1
    assert data["frequent_foods"][0]["canonical_name"] == "Empanadas"


@pytest.mark.asyncio
async def test_food_profile_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/users/me/food-profile")
    assert response.status_code in (401, 403)  # 401 Unauthorized (no bearer token)


# ── GET /admin/metrics/scan-confidence ───────────────────────────────────────


@pytest.mark.asyncio
async def test_scan_metrics_returns_403_for_non_admin(
    api_client: AsyncClient,
    auth_headers: dict,
) -> None:
    response = await api_client.get(
        "/api/v1/admin/metrics/scan-confidence",
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_scan_metrics_returns_200_for_admin(
    api_client: AsyncClient,
    test_user,
    auth_headers: dict,
    monkeypatch,
) -> None:
    # Set admin_emails to include the test user's email
    from app import config as config_module

    original_admin_emails = config_module.settings.admin_emails
    monkeypatch.setattr(config_module.settings, "admin_emails", test_user.email)

    try:
        response = await api_client.get(
            "/api/v1/admin/metrics/scan-confidence",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "avg_confidence" in data
        assert "count_low_confidence" in data
        assert "correction_rate" in data
        assert "days" in data
    finally:
        monkeypatch.setattr(
            config_module.settings, "admin_emails", original_admin_emails
        )
