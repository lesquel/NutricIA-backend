"""Unit tests for learning_loop application use cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.learning_loop.application.get_scan_metrics_use_case import (
    GetScanMetricsUseCase,
)
from app.learning_loop.application.track_scan_correction_use_case import (
    TrackScanCorrectionUseCase,
)
from app.learning_loop.application.update_food_profile_use_case import (
    UpdateFoodProfileUseCase,
)
from app.learning_loop.domain.entities import ScanCorrection, UserFoodProfile


def _profile(user_id: uuid.UUID) -> UserFoodProfile:
    return UserFoodProfile(
        user_id=user_id,
        frequent_foods=[{"canonical_name": "Rice", "count": 2}],
        avoided_tags=[],
        avg_daily_macros={"protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0},
        updated_at=datetime.now(timezone.utc),
    )


# ── UpdateFoodProfileUseCase ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_update_increments_frequent_foods() -> None:
    user_id = uuid.uuid4()
    existing = _profile(user_id)

    profile_repo = AsyncMock()
    profile_repo.get_by_user.return_value = existing
    profile_repo.upsert = AsyncMock(side_effect=lambda p: p)

    meal_query_fn = AsyncMock(return_value=[])

    use_case = UpdateFoodProfileUseCase(profile_repo, meal_query_fn)
    result = await use_case.execute(user_id, "Rice")

    rice = next(f for f in result.frequent_foods if f["canonical_name"] == "Rice")
    assert rice["count"] == 3  # was 2, now 3


@pytest.mark.asyncio
async def test_profile_update_adds_new_food() -> None:
    user_id = uuid.uuid4()
    existing = _profile(user_id)

    profile_repo = AsyncMock()
    profile_repo.get_by_user.return_value = existing
    profile_repo.upsert = AsyncMock(side_effect=lambda p: p)

    meal_query_fn = AsyncMock(return_value=[])
    use_case = UpdateFoodProfileUseCase(profile_repo, meal_query_fn)
    result = await use_case.execute(user_id, "Chicken")

    assert any(f["canonical_name"] == "Chicken" for f in result.frequent_foods)
    chicken = next(f for f in result.frequent_foods if f["canonical_name"] == "Chicken")
    assert chicken["count"] == 1


@pytest.mark.asyncio
async def test_profile_update_with_no_meals_sets_zero_macros() -> None:
    user_id = uuid.uuid4()

    profile_repo = AsyncMock()
    profile_repo.get_by_user.return_value = None  # no existing profile
    profile_repo.upsert = AsyncMock(side_effect=lambda p: p)

    meal_query_fn = AsyncMock(return_value=[])  # no meals
    use_case = UpdateFoodProfileUseCase(profile_repo, meal_query_fn)
    result = await use_case.execute(user_id, None)

    assert result.avg_daily_macros == {"protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}


@pytest.mark.asyncio
async def test_profile_update_averages_macros() -> None:
    user_id = uuid.uuid4()

    meal1 = MagicMock(protein_g=100.0, carbs_g=200.0, fat_g=50.0)
    meal2 = MagicMock(protein_g=60.0, carbs_g=100.0, fat_g=30.0)

    profile_repo = AsyncMock()
    profile_repo.get_by_user.return_value = None
    profile_repo.upsert = AsyncMock(side_effect=lambda p: p)

    meal_query_fn = AsyncMock(return_value=[meal1, meal2])
    use_case = UpdateFoodProfileUseCase(profile_repo, meal_query_fn)
    result = await use_case.execute(user_id, None)

    assert result.avg_daily_macros["protein_g"] == 80.0
    assert result.avg_daily_macros["carbs_g"] == 150.0
    assert result.avg_daily_macros["fat_g"] == 40.0


# ── TrackScanCorrectionUseCase ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_correction_skipped_for_high_confidence() -> None:
    repo = AsyncMock()
    use_case = TrackScanCorrectionUseCase(repo)

    result = await use_case.execute(
        user_id=uuid.uuid4(),
        meal_id=uuid.uuid4(),
        original_scan={"name": "Pizza"},
        corrected_values={"calories": 400},
        original_confidence=0.75,  # >= 0.6, should be skipped
    )
    assert result is None
    repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_correction_skipped_at_threshold() -> None:
    repo = AsyncMock()
    use_case = TrackScanCorrectionUseCase(repo)

    result = await use_case.execute(
        user_id=uuid.uuid4(),
        meal_id=uuid.uuid4(),
        original_scan={"name": "Burger"},
        corrected_values={"protein_g": 20},
        original_confidence=0.6,  # exactly 0.6, should be skipped
    )
    assert result is None
    repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_correction_persisted_for_low_confidence() -> None:
    user_id = uuid.uuid4()
    meal_id = uuid.uuid4()

    saved_correction = ScanCorrection(
        id=uuid.uuid4(),
        user_id=user_id,
        meal_id=meal_id,
        original_scan={"name": "Salad"},
        corrected_values={"calories": 150},
        original_confidence=0.35,
        created_at=datetime.now(timezone.utc),
    )
    repo = AsyncMock()
    repo.create.return_value = saved_correction

    use_case = TrackScanCorrectionUseCase(repo)
    result = await use_case.execute(
        user_id=user_id,
        meal_id=meal_id,
        original_scan={"name": "Salad"},
        corrected_values={"calories": 150},
        original_confidence=0.35,
    )
    assert result is not None
    assert result.original_confidence == 0.35
    repo.create.assert_called_once()


# ── GetScanMetricsUseCase ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_empty_corrections() -> None:
    repo = AsyncMock()
    repo.list_all.return_value = []

    use_case = GetScanMetricsUseCase(repo)
    result = await use_case.execute(user_id=None, days=30)

    assert result["avg_confidence"] == 0.0
    assert result["count_low_confidence"] == 0
    assert result["correction_rate"] == 0.0
    assert result["days"] == 30


@pytest.mark.asyncio
async def test_metrics_aggregation() -> None:
    uid = uuid.uuid4()
    mid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    corrections = [
        ScanCorrection(
            id=uuid.uuid4(),
            user_id=uid,
            meal_id=mid,
            original_scan={},
            corrected_values={},
            original_confidence=0.3,
            created_at=now,
        ),
        ScanCorrection(
            id=uuid.uuid4(),
            user_id=uid,
            meal_id=mid,
            original_scan={},
            corrected_values={},
            original_confidence=0.8,
            created_at=now,
        ),
        ScanCorrection(
            id=uuid.uuid4(),
            user_id=uid,
            meal_id=mid,
            original_scan={},
            corrected_values={},
            original_confidence=0.4,
            created_at=now,
        ),
    ]
    repo = AsyncMock()
    repo.list_all.return_value = corrections

    use_case = GetScanMetricsUseCase(repo)
    result = await use_case.execute(user_id=None, days=30)

    expected_avg = round((0.3 + 0.8 + 0.4) / 3, 4)
    assert result["avg_confidence"] == expected_avg
    assert result["count_low_confidence"] == 2  # 0.3 and 0.4 are < 0.6
    assert result["correction_rate"] == round(2 / 3, 4)
