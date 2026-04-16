"""Learning loop infrastructure — repository implementations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning_loop.domain.entities import ScanCorrection, UserFoodProfile
from app.learning_loop.infrastructure.models import (
    ScanCorrectionModel,
    UserFoodProfileModel,
)


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC, attaching tzinfo if missing."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class UserFoodProfileRepositoryImpl:
    """Implements UserFoodProfileRepositoryPort against SQLAlchemy AsyncSession."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_user(self, user_id: uuid.UUID) -> UserFoodProfile | None:
        result = await self._db.execute(
            select(UserFoodProfileModel).where(UserFoodProfileModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def upsert(self, profile: UserFoodProfile) -> UserFoodProfile:
        result = await self._db.execute(
            select(UserFoodProfileModel).where(
                UserFoodProfileModel.user_id == profile.user_id
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = UserFoodProfileModel(user_id=profile.user_id)
            self._db.add(row)

        row.set_frequent_foods(profile.frequent_foods)
        row.set_avoided_tags(profile.avoided_tags)
        row.set_avg_daily_macros(profile.avg_daily_macros)
        row.updated_at = _ensure_utc(profile.updated_at)

        await self._db.flush()
        await self._db.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: UserFoodProfileModel) -> UserFoodProfile:
        return UserFoodProfile(
            user_id=row.user_id,
            frequent_foods=row.get_frequent_foods(),
            avoided_tags=row.get_avoided_tags(),
            avg_daily_macros=row.get_avg_daily_macros(),
            updated_at=_ensure_utc(row.updated_at),
        )


class ScanCorrectionRepositoryImpl:
    """Implements ScanCorrectionRepositoryPort against SQLAlchemy AsyncSession."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, correction: ScanCorrection) -> ScanCorrection:
        row = ScanCorrectionModel(
            id=correction.id,
            user_id=correction.user_id,
            meal_id=correction.meal_id,
            original_confidence=correction.original_confidence,
            created_at=_ensure_utc(correction.created_at),
        )
        row.set_original_scan(correction.original_scan)
        row.set_corrected_values(correction.corrected_values)

        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return self._to_domain(row)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[ScanCorrection]:
        result = await self._db.execute(
            select(ScanCorrectionModel)
            .where(ScanCorrectionModel.user_id == user_id)
            .order_by(ScanCorrectionModel.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [self._to_domain(r) for r in rows]

    async def list_all(self, limit: int = 10_000) -> list[ScanCorrection]:
        """Return all corrections across all users (admin scope)."""
        result = await self._db.execute(
            select(ScanCorrectionModel)
            .order_by(ScanCorrectionModel.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: ScanCorrectionModel) -> ScanCorrection:
        return ScanCorrection(
            id=row.id,
            user_id=row.user_id,
            meal_id=row.meal_id,
            original_scan=row.get_original_scan(),
            corrected_values=row.get_corrected_values(),
            original_confidence=row.original_confidence,
            created_at=_ensure_utc(row.created_at),
        )
