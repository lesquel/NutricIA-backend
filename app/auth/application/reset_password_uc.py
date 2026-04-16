"""Use case: Reset password using a valid reset token."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.domain import TokenExpiredError, TokenAlreadyUsedError, TokenNotFoundError
from app.auth.infrastructure.repository import (
    get_user_by_id,
    hash_password,
)
from app.auth.infrastructure.reset_token_repo import PasswordResetTokenRepositoryImpl

logger = logging.getLogger("nutricia.auth")


async def reset_password(
    db: AsyncSession,
    raw_token: str,
    new_password: str,
) -> None:
    """Reset user password using a valid, non-expired, unused token.

    Raises:
        TokenNotFoundError: token does not exist.
        TokenAlreadyUsedError: token was already used.
        TokenExpiredError: token has passed its expiry time.
        ValueError: user referenced by token not found.
    """
    repo = PasswordResetTokenRepositoryImpl(db)
    token_entity = await repo.find_by_token(raw_token)

    if token_entity is None:
        raise TokenNotFoundError()

    if token_entity.used:
        raise TokenAlreadyUsedError()

    now = datetime.now(timezone.utc)
    if token_entity.is_expired(now):
        raise TokenExpiredError()

    user = await get_user_by_id(db, str(token_entity.user_id))
    if user is None:
        raise ValueError("User not found")

    user.password_hash = hash_password(new_password)
    await repo.mark_used(token_entity.id)
    await db.flush()
