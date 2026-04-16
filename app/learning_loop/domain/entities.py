"""Learning loop domain entities — no framework dependencies.

Macros is redefined here to keep modules independent (no cross-domain imports).
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class UserFoodProfile:
    """Evolving profile of a user's food habits, built from scan history."""

    user_id: uuid.UUID
    frequent_foods: list[dict[str, Any]]  # [{canonical_name, count}]
    avoided_tags: list[str]
    avg_daily_macros: dict[str, Any]  # {protein_g, carbs_g, fat_g}
    updated_at: datetime

    def add_food(self, canonical_name: str) -> UserFoodProfile:
        """Return a new profile with the given food's count incremented (or added)."""
        new_foods = copy.deepcopy(self.frequent_foods)
        for entry in new_foods:
            if entry["canonical_name"] == canonical_name:
                entry["count"] = int(entry["count"]) + 1
                break
        else:
            new_foods.append({"canonical_name": canonical_name, "count": 1})

        return UserFoodProfile(
            user_id=self.user_id,
            frequent_foods=new_foods,
            avoided_tags=list(self.avoided_tags),
            avg_daily_macros=dict(self.avg_daily_macros),
            updated_at=self.updated_at,
        )

    def is_frequent(self, canonical_name: str, threshold: int = 3) -> bool:
        """Return True if the food has been eaten at least `threshold` times."""
        for entry in self.frequent_foods:
            if entry["canonical_name"] == canonical_name:
                return bool(int(entry["count"]) >= threshold)
        return False


@dataclass
class ScanCorrection:
    """Records what the user corrected after an AI food scan."""

    id: uuid.UUID
    user_id: uuid.UUID
    meal_id: uuid.UUID
    original_scan: dict[str, Any]
    corrected_values: dict[str, Any]
    original_confidence: float  # must be in [0, 1]
    created_at: datetime

    def __post_init__(self) -> None:
        if not (0.0 <= self.original_confidence <= 1.0):
            raise ValueError(
                f"original_confidence must be in [0, 1], got {self.original_confidence}"
            )
