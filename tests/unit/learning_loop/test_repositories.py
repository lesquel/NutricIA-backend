"""Unit tests for learning_loop infrastructure repositories."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning_loop.domain.entities import ScanCorrection, UserFoodProfile
from app.learning_loop.infrastructure.repositories import (
    ScanCorrectionRepositoryImpl,
    UserFoodProfileRepositoryImpl,
)


def _make_profile(user_id: uuid.UUID) -> UserFoodProfile:
    return UserFoodProfile(
        user_id=user_id,
        frequent_foods=[{"canonical_name": "Rice", "count": 3}],
        avoided_tags=["spicy"],
        avg_daily_macros={"protein_g": 80.0, "carbs_g": 200.0, "fat_g": 60.0},
        updated_at=datetime.now(timezone.utc),
    )


# ── UserFoodProfileRepository ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_create_and_get_by_user(
    db_session: AsyncSession,
    test_user,
) -> None:
    repo = UserFoodProfileRepositoryImpl(db_session)
    profile = _make_profile(test_user.id)

    saved = await repo.upsert(profile)
    fetched = await repo.get_by_user(test_user.id)

    assert fetched is not None
    assert fetched.user_id == test_user.id
    assert fetched.frequent_foods == [{"canonical_name": "Rice", "count": 3}]
    assert fetched.avoided_tags == ["spicy"]
    assert fetched.avg_daily_macros["protein_g"] == 80.0


@pytest.mark.asyncio
async def test_profile_returns_none_when_not_found(
    db_session: AsyncSession,
) -> None:
    repo = UserFoodProfileRepositoryImpl(db_session)
    result = await repo.get_by_user(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_profile_upsert_updates_existing(
    db_session: AsyncSession,
    test_user,
) -> None:
    repo = UserFoodProfileRepositoryImpl(db_session)
    profile = _make_profile(test_user.id)
    await repo.upsert(profile)

    updated = UserFoodProfile(
        user_id=test_user.id,
        frequent_foods=[
            {"canonical_name": "Rice", "count": 5},
            {"canonical_name": "Chicken", "count": 2},
        ],
        avoided_tags=[],
        avg_daily_macros={"protein_g": 100.0, "carbs_g": 250.0, "fat_g": 70.0},
        updated_at=datetime.now(timezone.utc),
    )
    await repo.upsert(updated)

    fetched = await repo.get_by_user(test_user.id)
    assert fetched is not None
    assert len(fetched.frequent_foods) == 2
    rice = next(f for f in fetched.frequent_foods if f["canonical_name"] == "Rice")
    assert rice["count"] == 5
    assert fetched.avg_daily_macros["protein_g"] == 100.0


# ── ScanCorrectionRepository ──────────────────────────────────────────────────


def _make_meal(db_session: AsyncSession, user_id: uuid.UUID):
    """Helper: create a minimal Meal row and return its id."""
    from app.meals.infrastructure import Meal

    meal = Meal(
        user_id=user_id,
        name="Test Meal",
        calories=400,
        protein_g=30,
        carbs_g=50,
        fat_g=15,
        confidence_score=0.4,
    )
    db_session.add(meal)
    return meal


@pytest.mark.asyncio
async def test_scan_correction_create(
    db_session: AsyncSession,
    test_user,
) -> None:
    meal = _make_meal(db_session, test_user.id)
    await db_session.flush()

    repo = ScanCorrectionRepositoryImpl(db_session)
    correction = ScanCorrection(
        id=uuid.uuid4(),
        user_id=test_user.id,
        meal_id=meal.id,
        original_scan={"name": "Pizza", "calories": 500},
        corrected_values={"calories": 450},
        original_confidence=0.3,
        created_at=datetime.now(timezone.utc),
    )
    saved = await repo.create(correction)
    assert saved.id == correction.id
    assert saved.original_scan == {"name": "Pizza", "calories": 500}
    assert saved.corrected_values == {"calories": 450}
    assert saved.original_confidence == 0.3


@pytest.mark.asyncio
async def test_scan_correction_list_ordering(
    db_session: AsyncSession,
    test_user,
) -> None:
    from datetime import timedelta

    meal = _make_meal(db_session, test_user.id)
    await db_session.flush()

    repo = ScanCorrectionRepositoryImpl(db_session)
    base_time = datetime.now(timezone.utc)

    for i in range(3):
        c = ScanCorrection(
            id=uuid.uuid4(),
            user_id=test_user.id,
            meal_id=meal.id,
            original_scan={"step": i},
            corrected_values={"step": i + 1},
            original_confidence=0.4,
            created_at=base_time + timedelta(seconds=i),
        )
        await repo.create(c)

    corrections = await repo.list_for_user(test_user.id, limit=10)
    assert len(corrections) == 3
    # Latest first
    assert corrections[0].created_at >= corrections[1].created_at
    assert corrections[1].created_at >= corrections[2].created_at
