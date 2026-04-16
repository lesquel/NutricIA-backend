"""Tests for scan prompt enrichment with user food profile."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.meals.infrastructure.ai_providers import (
    _build_scan_message,
    _build_user_context_block,
)


# ── Context block builder ─────────────────────────────────────────────────────


def test_context_block_includes_top_5_foods() -> None:
    profile_hint = {
        "frequent_foods": [
            {"canonical_name": "Rice", "count": 10},
            {"canonical_name": "Chicken", "count": 8},
            {"canonical_name": "Eggs", "count": 6},
            {"canonical_name": "Banana", "count": 5},
            {"canonical_name": "Oatmeal", "count": 4},
            {"canonical_name": "Coffee", "count": 2},  # 6th — should be excluded
        ],
        "avg_daily_macros": {"protein_g": 80, "carbs_g": 200, "fat_g": 60},
    }
    block = _build_user_context_block(profile_hint)
    assert "Rice" in block
    assert "Chicken" in block
    assert "Oatmeal" in block
    assert "Coffee" not in block  # 6th food excluded


def test_context_block_includes_macros() -> None:
    profile_hint = {
        "frequent_foods": [{"canonical_name": "Pizza", "count": 5}],
        "avg_daily_macros": {"protein_g": 90, "carbs_g": 250, "fat_g": 70},
    }
    block = _build_user_context_block(profile_hint)
    assert "90" in block  # protein
    assert "250" in block  # carbs
    assert "70" in block  # fat


def test_context_block_empty_when_no_foods() -> None:
    profile_hint = {
        "frequent_foods": [],
        "avg_daily_macros": {"protein_g": 0, "carbs_g": 0, "fat_g": 0},
    }
    block = _build_user_context_block(profile_hint)
    assert block == ""


def test_context_block_uses_user_context_tag() -> None:
    profile_hint = {
        "frequent_foods": [{"canonical_name": "Salad", "count": 3}],
        "avg_daily_macros": {"protein_g": 50, "carbs_g": 100, "fat_g": 30},
    }
    block = _build_user_context_block(profile_hint)
    assert "<user_context>" in block
    assert "</user_context>" in block


# ── Scan message builder ──────────────────────────────────────────────────────


def test_scan_message_no_profile_uses_base_prompt() -> None:
    image_bytes = b"\xff\xd8\xff" + b"\x00" * 100  # minimal JPEG header
    msg = _build_scan_message(image_bytes, "image/jpeg", user_food_profile_hint=None)
    text_block = msg.content[0]
    assert text_block["type"] == "text"
    assert "<user_context>" not in text_block["text"]


def test_scan_message_with_profile_prepends_context() -> None:
    image_bytes = b"\xff\xd8\xff" + b"\x00" * 100
    profile_hint = {
        "frequent_foods": [{"canonical_name": "Empanadas", "count": 7}],
        "avg_daily_macros": {"protein_g": 60, "carbs_g": 180, "fat_g": 55},
    }
    msg = _build_scan_message(
        image_bytes, "image/jpeg", user_food_profile_hint=profile_hint
    )
    text_block = msg.content[0]
    assert text_block["type"] == "text"
    assert "<user_context>" in text_block["text"]
    assert "Empanadas" in text_block["text"]


def test_scan_message_with_empty_profile_no_context() -> None:
    """Profile with no foods should NOT inject user_context block."""
    image_bytes = b"\xff\xd8\xff" + b"\x00" * 100
    profile_hint = {
        "frequent_foods": [],
        "avg_daily_macros": {"protein_g": 0, "carbs_g": 0, "fat_g": 0},
    }
    msg = _build_scan_message(
        image_bytes, "image/jpeg", user_food_profile_hint=profile_hint
    )
    text_block = msg.content[0]
    assert "<user_context>" not in text_block["text"]
