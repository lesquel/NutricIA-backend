"""Unit tests for password reset use cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.application.request_password_reset_uc import (
    RESET_TOKEN_TTL_MINUTES,
    request_password_reset,
)
from app.auth.application.reset_password_uc import reset_password
from app.auth.domain import (
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenNotFoundError,
)
from app.auth.domain.entities import PasswordResetToken
from app.auth.infrastructure.models import PasswordResetTokenModel, User
from app.auth.infrastructure.repository import hash_password, verify_password
from app.auth.infrastructure.reset_token_repo import PasswordResetTokenRepositoryImpl


@pytest.fixture
def email_adapter_mock() -> AsyncMock:
    """Mock EmailPort adapter that records calls."""
    mock = AsyncMock()
    mock.send_reset_email = AsyncMock(return_value=None)
    return mock


# ── request_password_reset ──────────────────────


@pytest.mark.asyncio
async def test_request_password_reset_creates_token_for_existing_user(
    db_session: AsyncSession,
    test_user: User,
    email_adapter_mock: AsyncMock,
) -> None:
    await request_password_reset(db_session, test_user.email, email_adapter_mock)

    # A token row exists for this user
    repo = PasswordResetTokenRepositoryImpl(db_session)
    # We need to query by user_id — verify via email adapter invocation
    email_adapter_mock.send_reset_email.assert_awaited_once()
    call_kwargs = email_adapter_mock.send_reset_email.await_args.kwargs
    assert call_kwargs["to"] == test_user.email
    assert len(call_kwargs["token"]) >= 32  # token_urlsafe(32) ~ 43 chars

    # Verify token persisted and not expired
    token_entity = await repo.find_by_token(call_kwargs["token"])
    assert token_entity is not None
    assert token_entity.user_id == test_user.id
    assert token_entity.used is False
    now = datetime.now(timezone.utc)
    assert token_entity.expires_at > now
    assert token_entity.expires_at <= now + timedelta(
        minutes=RESET_TOKEN_TTL_MINUTES + 1
    )


@pytest.mark.asyncio
async def test_request_password_reset_silent_for_unknown_email(
    db_session: AsyncSession,
    email_adapter_mock: AsyncMock,
) -> None:
    # Unknown email → must NOT raise and must NOT send email (no user enumeration)
    await request_password_reset(db_session, "unknown@example.com", email_adapter_mock)

    email_adapter_mock.send_reset_email.assert_not_awaited()


# ── reset_password ──────────────────────


async def _insert_token(
    db_session: AsyncSession,
    user: User,
    *,
    raw_token: str = "valid-test-token-123",
    expires_in_minutes: int = 15,
    used: bool = False,
) -> PasswordResetToken:
    token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=raw_token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        used=used,
    )
    repo = PasswordResetTokenRepositoryImpl(db_session)
    await repo.create(token)
    return token


@pytest.mark.asyncio
async def test_reset_password_with_valid_token_updates_password(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    original_hash = test_user.password_hash
    raw_token = "fresh-valid-token"
    await _insert_token(db_session, test_user, raw_token=raw_token)

    await reset_password(db_session, raw_token, "brand-new-password-456")
    await db_session.commit()
    await db_session.refresh(test_user)

    # Password changed
    assert test_user.password_hash != original_hash
    assert verify_password("brand-new-password-456", test_user.password_hash)

    # Token marked as used
    repo = PasswordResetTokenRepositoryImpl(db_session)
    token_after = await repo.find_by_token(raw_token)
    assert token_after is not None
    assert token_after.used is True


@pytest.mark.asyncio
async def test_reset_password_with_nonexistent_token_raises(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(TokenNotFoundError):
        await reset_password(db_session, "does-not-exist", "newpassword123")


@pytest.mark.asyncio
async def test_reset_password_with_expired_token_raises(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    raw_token = "expired-token"
    await _insert_token(
        db_session, test_user, raw_token=raw_token, expires_in_minutes=-1
    )

    with pytest.raises(TokenExpiredError):
        await reset_password(db_session, raw_token, "newpassword123")


@pytest.mark.asyncio
async def test_reset_password_with_used_token_raises(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    raw_token = "already-used-token"
    await _insert_token(db_session, test_user, raw_token=raw_token, used=True)

    with pytest.raises(TokenAlreadyUsedError):
        await reset_password(db_session, raw_token, "newpassword123")


@pytest.mark.asyncio
async def test_reset_password_preserves_token_single_use(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """A successful reset marks token as used — second attempt must fail."""
    raw_token = "single-use-token"
    await _insert_token(db_session, test_user, raw_token=raw_token)

    await reset_password(db_session, raw_token, "firstpassword123")
    await db_session.commit()

    with pytest.raises(TokenAlreadyUsedError):
        await reset_password(db_session, raw_token, "secondpassword456")
