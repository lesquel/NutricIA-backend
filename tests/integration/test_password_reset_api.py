"""Integration tests for forgot-password and reset-password endpoints."""

from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import User
from app.auth.infrastructure import rate_limiter
from app.auth.infrastructure.repository import verify_password


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    """Nuke ALL rate limit state before and after each test.

    The module-level `_rate_store` persists across tests; without a full
    clear, parallel or sequential tests that share an IP key get 429.
    """
    rate_limiter._rate_store.clear()
    yield
    rate_limiter._rate_store.clear()


# ── POST /auth/forgot-password ──────────────────────


@pytest.mark.asyncio
async def test_forgot_password_existing_email_returns_200(
    api_client: AsyncClient,
    test_user: User,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="nutricia.notifications")
    response = await api_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user.email},
    )

    assert response.status_code == 200
    body = response.json()
    assert "message" in body

    # Dev mode logs the reset token via ConsoleEmailAdapter
    assert any("RESET_TOKEN" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_200_no_enumeration(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "totally-unknown@example.com"},
    )

    assert response.status_code == 200
    body = response.json()
    # Generic response — same shape as for existing emails (prevents enumeration)
    assert "message" in body


@pytest.mark.asyncio
async def test_forgot_password_rate_limited_returns_429(
    api_client: AsyncClient,
    test_user: User,
) -> None:
    # First request succeeds
    first = await api_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user.email},
    )
    assert first.status_code == 200

    # Immediate second request → 429
    second = await api_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user.email},
    )
    assert second.status_code == 429
    assert "rate limit" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_forgot_password_invalid_email_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "not-an-email"},
    )
    assert response.status_code == 422


# ── POST /auth/reset-password ──────────────────────


async def _request_reset_and_grab_token(
    api_client: AsyncClient,
    db_session: AsyncSession,
    user: User,
) -> str:
    """Helper: trigger forgot-password and fetch the raw token from DB."""
    rate_limiter._rate_store.clear()
    response = await api_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
    )
    assert response.status_code == 200

    # Find the created token in DB
    from sqlalchemy import select

    from app.auth.infrastructure.models import PasswordResetTokenModel

    result = await db_session.execute(
        select(PasswordResetTokenModel).where(
            PasswordResetTokenModel.user_id == user.id
        )
    )
    token_row = result.scalar_one()
    return str(token_row.token)


@pytest.mark.asyncio
async def test_reset_password_with_valid_token_returns_200(
    api_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    raw_token = await _request_reset_and_grab_token(api_client, db_session, test_user)

    response = await api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "new-secure-pw-789"},
    )
    assert response.status_code == 200

    # New password works, old doesn't
    await db_session.refresh(test_user)
    assert verify_password("new-secure-pw-789", test_user.password_hash)


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token_returns_400(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "does-not-exist-anywhere", "new_password": "newpassword123"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_cannot_be_reused(
    api_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    raw_token = await _request_reset_and_grab_token(api_client, db_session, test_user)

    # First reset succeeds
    first = await api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "first-password-abc"},
    )
    assert first.status_code == 200

    # Second reset with same token fails
    second = await api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "second-password-xyz"},
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_short_password_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "anything", "new_password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_empty_token_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "   ", "new_password": "validpassword"},
    )
    assert response.status_code == 422
