"""Use case: Request password reset (forgot-password flow)."""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.domain.entities import PasswordResetToken
from app.auth.infrastructure.repository import get_user_by_email
from app.auth.infrastructure.reset_token_repo import PasswordResetTokenRepositoryImpl
from app.config import settings
from app.notifications.domain.ports import EmailPort

logger = logging.getLogger("nutricia.auth")

RESET_TOKEN_TTL_MINUTES = 15


async def request_password_reset(
    db: AsyncSession,
    email: str,
    email_adapter: EmailPort,
) -> None:
    """Request a password reset for the given email.

    Always returns without error — unknown emails receive the same response
    as registered ones (no user enumeration).
    """
    user = await get_user_by_email(db, email)
    if user is None:
        # No user enumeration: silently succeed
        logger.debug("Password reset requested for unknown email: %s", email)
        return

    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)

    token_entity = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=raw_token,
        expires_at=expires_at,
        used=False,
    )

    repo = PasswordResetTokenRepositoryImpl(db)
    await repo.create(token_entity)

    reset_url = f"{settings.frontend_deep_link_base}reset-password?token={raw_token}"

    await email_adapter.send_reset_email(
        to=email,
        token=raw_token,
        reset_url=reset_url,
    )
