"""Use case: Track scan corrections for learning loop feedback."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.learning_loop.domain.entities import ScanCorrection
from app.learning_loop.domain.ports import ScanCorrectionRepositoryPort

LOW_CONFIDENCE_THRESHOLD = 0.6


class TrackScanCorrectionUseCase:
    """Records user corrections to AI scans — only for low-confidence results."""

    def __init__(self, scan_correction_repo: ScanCorrectionRepositoryPort) -> None:
        self._repo = scan_correction_repo

    async def execute(
        self,
        user_id: uuid.UUID,
        meal_id: uuid.UUID,
        original_scan: dict[str, Any],
        corrected_values: dict[str, Any],
        original_confidence: float,
    ) -> ScanCorrection | None:
        """Persist a correction only when original_confidence < 0.6.

        Returns None (silently skipped) when confidence is at or above the threshold.
        """
        if original_confidence >= LOW_CONFIDENCE_THRESHOLD:
            return None

        correction = ScanCorrection(
            id=uuid.uuid4(),
            user_id=user_id,
            meal_id=meal_id,
            original_scan=original_scan,
            corrected_values=corrected_values,
            original_confidence=original_confidence,
            created_at=datetime.now(timezone.utc),
        )
        return await self._repo.create(correction)
