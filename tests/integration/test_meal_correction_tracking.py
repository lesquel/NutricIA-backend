"""Integration tests for scan correction tracking via PATCH /meals/{meal_id}."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning_loop.infrastructure.models import ScanCorrectionModel
from app.meals.infrastructure import Meal


async def _create_meal(
    db_session: AsyncSession,
    user_id: uuid.UUID,
    confidence_score: float = 0.4,
) -> Meal:
    """Create a minimal meal for testing."""
    meal = Meal(
        user_id=user_id,
        name="Test AI Meal",
        calories=500,
        protein_g=30,
        carbs_g=60,
        fat_g=20,
        meal_type="lunch",
        confidence_score=confidence_score,
        ai_raw_response=json.dumps(
            {
                "name": "Test AI Meal",
                "calories": 500,
                "confidence": confidence_score,
            }
        ),
    )
    db_session.add(meal)
    await db_session.flush()
    await db_session.refresh(meal)
    return meal


@pytest.mark.asyncio
async def test_patch_low_confidence_meal_creates_correction(
    api_client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session: AsyncSession,
) -> None:
    """PATCH a low-confidence meal → scan_corrections row is created."""
    meal = await _create_meal(db_session, test_user.id, confidence_score=0.4)
    await db_session.commit()

    response = await api_client.patch(
        f"/api/v1/meals/{meal.id}",
        headers=auth_headers,
        json={"calories": 450, "protein_g": 35},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["calories"] == 450
    assert data["protein_g"] == 35

    # Background tasks run inline in test (ASGI transport runs them synchronously)
    # Wait briefly if needed — but BackgroundTasks in TestClient are run inline
    result = await db_session.execute(
        select(ScanCorrectionModel).where(ScanCorrectionModel.meal_id == meal.id)
    )
    corrections = list(result.scalars().all())
    assert len(corrections) == 1
    correction = corrections[0]
    assert correction.original_confidence == 0.4
    corrected = json.loads(correction.corrected_values)
    assert corrected["calories"] == 450


@pytest.mark.asyncio
async def test_patch_high_confidence_meal_no_correction(
    api_client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session: AsyncSession,
) -> None:
    """PATCH a high-confidence meal → no scan_corrections row."""
    meal = await _create_meal(db_session, test_user.id, confidence_score=0.9)
    await db_session.commit()

    response = await api_client.patch(
        f"/api/v1/meals/{meal.id}",
        headers=auth_headers,
        json={"calories": 480},
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(ScanCorrectionModel).where(ScanCorrectionModel.meal_id == meal.id)
    )
    corrections = list(result.scalars().all())
    assert len(corrections) == 0


@pytest.mark.asyncio
async def test_patch_meal_not_found_returns_404(
    api_client: AsyncClient,
    auth_headers: dict,
) -> None:
    response = await api_client.patch(
        f"/api/v1/meals/{uuid.uuid4()}",
        headers=auth_headers,
        json={"calories": 300},
    )
    assert response.status_code == 404
