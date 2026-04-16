"""Learning loop presentation — Pydantic schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class UserFoodProfileResponse(BaseModel):
    user_id: str
    frequent_foods: list[dict[str, Any]]
    avoided_tags: list[str]
    avg_daily_macros: dict[str, Any]
    updated_at: str


class ScanMetricsResponse(BaseModel):
    avg_confidence: float
    count_low_confidence: int
    correction_rate: float
    days: int
