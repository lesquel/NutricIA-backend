"""Auth infrastructure — PasswordResetToken repository implementation."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.domain.entities import PasswordResetToken
from app.auth.infrastructure.models import PasswordResetTokenModel


def _ensure_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC tzinfo to naive datetimes returned by SQLite.

    Postgres preserves timezone on `DateTime(timezone=True)`, but SQLite
    strips it on read. Since we always store UTC, we safely re-attach it.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _model_to_entity(model: PasswordResetTokenModel) -> PasswordResetToken:
    return PasswordResetToken(
        id=model.id,
        user_id=model.user_id,
        token=model.token,
        expires_at=_ensure_utc(model.expires_at),  # type: ignore[arg-type]
        used=model.used,
        created_at=_ensure_utc(model.created_at),
    )


class PasswordResetTokenRepositoryImpl:
    """SQLAlchemy async implementation of PasswordResetTokenRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        model = PasswordResetTokenModel(
            id=token.id,
            user_id=token.user_id,
            token=token.token,
            expires_at=token.expires_at,
            used=token.used,
        )
        self._db.add(model)
        await self._db.flush()
        await self._db.refresh(model)
        return _model_to_entity(model)

    async def find_by_token(self, token: str) -> PasswordResetToken | None:
        result = await self._db.execute(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.token == token
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_entity(model)

    async def mark_used(self, token_id: uuid.UUID) -> None:
        await self._db.execute(
            update(PasswordResetTokenModel)
            .where(PasswordResetTokenModel.id == token_id)
            .values(used=True)
        )
        await self._db.flush()
