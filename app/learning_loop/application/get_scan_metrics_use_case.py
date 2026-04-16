"""Use case: Aggregate scan correction metrics for admin dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.learning_loop.domain.ports import ScanCorrectionRepositoryPort

LOW_CONFIDENCE_THRESHOLD = 0.6


class GetScanMetricsUseCase:
    """Compute scan quality metrics from the corrections table.

    When user_id is None, operates over all users (admin scope).
    """

    def __init__(self, scan_correction_repo: ScanCorrectionRepositoryPort) -> None:
        self._repo = scan_correction_repo

    async def execute(
        self,
        user_id: uuid.UUID | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        # list_for_user fetches up to 50 recent corrections; use a high limit for admin
        limit = 10_000
        if user_id is not None:
            corrections = await self._repo.list_for_user(user_id, limit=limit)
        else:
            corrections = await self._repo.list_all(limit=limit)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        corrections = [c for c in corrections if c.created_at >= cutoff]

        total = len(corrections)
        if total == 0:
            return {
                "avg_confidence": 0.0,
                "count_low_confidence": 0,
                "correction_rate": 0.0,
                "days": days,
            }

        avg_confidence = sum(c.original_confidence for c in corrections) / total
        count_low = sum(
            1 for c in corrections if c.original_confidence < LOW_CONFIDENCE_THRESHOLD
        )
        correction_rate = round(count_low / total, 4)

        return {
            "avg_confidence": round(avg_confidence, 4),
            "count_low_confidence": count_low,
            "correction_rate": correction_rate,
            "days": days,
        }
