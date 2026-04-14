"""Use case: Email/Password register & login.

Handles traditional JWT authentication alongside OAuth.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.domain import EmailAlreadyExistsError, InvalidCredentialsError
from app.auth.infrastructure.repository import (
    create_email_user,
    create_refresh_token_record,
    get_user_by_email,
    verify_password,
)
from app.auth.presentation import TokenResponse
from app.auth.application.oauth_login import user_to_profile
from app.config import Settings
from app.shared.infrastructure.security import create_access_token, create_refresh_token


async def register(
    db: AsyncSession,
    email: str,
    password: str,
    name: str,
) -> TokenResponse:
    """Register a new user with email + password and return JWT."""
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise EmailAlreadyExistsError()

    user = await create_email_user(db, email, name, password)
    token = create_access_token(str(user.id))
    raw_refresh, token_hash = create_refresh_token(str(user.id))
    settings = Settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_expire_days
    )
    await create_refresh_token_record(db, user.id, token_hash, expires_at)
    profile = user_to_profile(user)

    return TokenResponse(access_token=token, refresh_token=raw_refresh, user=profile)


async def login(
    db: AsyncSession,
    email: str,
    password: str,
) -> TokenResponse:
    """Authenticate with email + password and return JWT."""
    user = await get_user_by_email(db, email)

    if user is None:
        raise InvalidCredentialsError()

    if not user.password_hash:
        # User exists but registered via OAuth, no password set
        raise InvalidCredentialsError(
            "This account was created via OAuth. Use Google or Apple sign-in, "
            "or set a password first."
        )

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()

    token = create_access_token(str(user.id))
    raw_refresh, token_hash = create_refresh_token(str(user.id))
    settings = Settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_expire_days
    )
    await create_refresh_token_record(db, user.id, token_hash, expires_at)
    profile = user_to_profile(user)

    return TokenResponse(access_token=token, refresh_token=raw_refresh, user=profile)
