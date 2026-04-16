"""Unit tests for learning_loop domain entities."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.learning_loop.domain.entities import ScanCorrection, UserFoodProfile


# ── UserFoodProfile ──────────────────────────────────────────


def _base_profile(user_id: uuid.UUID | None = None) -> UserFoodProfile:
    return UserFoodProfile(
        user_id=user_id or uuid.uuid4(),
        frequent_foods=[],
        avoided_tags=[],
        avg_daily_macros={"protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0},
        updated_at=datetime.now(timezone.utc),
    )


def test_add_food_adds_new_entry_for_unseen_food() -> None:
    profile = _base_profile()
    updated = profile.add_food("pollo")
    assert len(updated.frequent_foods) == 1
    assert updated.frequent_foods[0]["canonical_name"] == "pollo"
    assert updated.frequent_foods[0]["count"] == 1


def test_add_food_increments_count_for_existing_food() -> None:
    profile = _base_profile()
    p1 = profile.add_food("pollo")
    p2 = p1.add_food("pollo")
    assert len(p2.frequent_foods) == 1
    assert p2.frequent_foods[0]["count"] == 2


def test_add_food_tracks_multiple_distinct_foods() -> None:
    profile = _base_profile()
    p = profile.add_food("pollo").add_food("arroz").add_food("pollo")
    names = {f["canonical_name"] for f in p.frequent_foods}
    assert names == {"pollo", "arroz"}
    pollo_entry = next(f for f in p.frequent_foods if f["canonical_name"] == "pollo")
    assert pollo_entry["count"] == 2


def test_add_food_does_not_mutate_original() -> None:
    profile = _base_profile()
    profile.add_food("pollo")
    assert profile.frequent_foods == []


def test_is_frequent_below_threshold_returns_false() -> None:
    profile = _base_profile()
    p = profile.add_food("pollo").add_food("pollo")
    assert p.is_frequent("pollo", threshold=3) is False


def test_is_frequent_at_threshold_returns_true() -> None:
    profile = _base_profile()
    p = profile.add_food("pollo").add_food("pollo").add_food("pollo")
    assert p.is_frequent("pollo", threshold=3) is True


def test_is_frequent_above_threshold_returns_true() -> None:
    profile = _base_profile()
    p = profile
    for _ in range(5):
        p = p.add_food("pollo")
    assert p.is_frequent("pollo", threshold=3) is True


def test_is_frequent_for_unknown_food_returns_false() -> None:
    profile = _base_profile()
    assert profile.is_frequent("unknown-food") is False


def test_is_frequent_default_threshold_is_three() -> None:
    profile = _base_profile()
    p = profile.add_food("pollo").add_food("pollo")
    assert p.is_frequent("pollo") is False
    p2 = p.add_food("pollo")
    assert p2.is_frequent("pollo") is True


# ── ScanCorrection ───────────────────────────────────────────


def _valid_correction(**overrides: object) -> ScanCorrection:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "meal_id": uuid.uuid4(),
        "original_scan": {"name": "Milanesa", "calories": 450},
        "corrected_values": {"calories": 380},
        "original_confidence": 0.75,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return ScanCorrection(**defaults)  # type: ignore[arg-type]


def test_scan_correction_valid() -> None:
    c = _valid_correction()
    assert c.original_confidence == 0.75


def test_scan_correction_rejects_confidence_above_one() -> None:
    with pytest.raises(ValueError, match="original_confidence"):
        _valid_correction(original_confidence=1.01)


def test_scan_correction_rejects_confidence_below_zero() -> None:
    with pytest.raises(ValueError, match="original_confidence"):
        _valid_correction(original_confidence=-0.01)


def test_scan_correction_confidence_zero_is_valid() -> None:
    c = _valid_correction(original_confidence=0.0)
    assert c.original_confidence == 0.0


def test_scan_correction_confidence_one_is_valid() -> None:
    c = _valid_correction(original_confidence=1.0)
    assert c.original_confidence == 1.0
