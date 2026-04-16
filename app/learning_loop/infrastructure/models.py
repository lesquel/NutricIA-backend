"""Learning loop infrastructure — SQLAlchemy models.

Maps user_food_profile and scan_corrections tables.
JSON columns use Text for SQLite compatibility; PostgreSQL uses JSONB.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure import Base


class UserFoodProfileModel(Base):
    """ORM mapping for user_food_profile table (migration 007)."""

    __tablename__ = "user_food_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    # Stored as JSON text; JSONB in postgres via migration DDL
    frequent_foods: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="[]"
    )
    avoided_tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    avg_daily_macros: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── JSON helpers ──────────────────────────────────────────────

    def get_frequent_foods(self) -> list[dict]:
        try:
            return json.loads(self.frequent_foods) if self.frequent_foods else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_frequent_foods(self, value: list[dict]) -> None:
        self.frequent_foods = json.dumps(value)

    def get_avoided_tags(self) -> list[str]:
        try:
            return json.loads(self.avoided_tags) if self.avoided_tags else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_avoided_tags(self, value: list[str]) -> None:
        self.avoided_tags = json.dumps(value)

    def get_avg_daily_macros(self) -> dict:
        try:
            return (
                json.loads(self.avg_daily_macros)
                if self.avg_daily_macros
                else {"protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
            )
        except (json.JSONDecodeError, TypeError):
            return {"protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}

    def set_avg_daily_macros(self, value: dict) -> None:
        self.avg_daily_macros = json.dumps(value)


class ScanCorrectionModel(Base):
    """ORM mapping for scan_corrections table (migration 010)."""

    __tablename__ = "scan_corrections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    meal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("meals.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_scan: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_values: Mapped[str] = mapped_column(Text, nullable=False)
    original_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── JSON helpers ──────────────────────────────────────────────

    def get_original_scan(self) -> dict[str, Any]:
        try:
            parsed: Any = json.loads(self.original_scan)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_original_scan(self, value: dict[str, Any]) -> None:
        self.original_scan = json.dumps(value)

    def get_corrected_values(self) -> dict[str, Any]:
        try:
            parsed: Any = json.loads(self.corrected_values)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_corrected_values(self, value: dict[str, Any]) -> None:
        self.corrected_values = json.dumps(value)
