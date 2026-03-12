import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.application.email_auth import login
from app.auth.domain import InvalidCredentialsError
from app.shared.infrastructure.security import decode_access_token
from app.auth.infrastructure.repository import hash_password
from app.auth.infrastructure.models import User
import uuid


@pytest.mark.asyncio
async def test_login_success_returns_token(db_session: AsyncSession):
    """Test that logging in with correct credentials returns a valid token."""
    user = User(
        id=uuid.uuid4(),
        email="logintest@example.com",
        name="Login Test User",
        password_hash=hash_password("mypassword123"),
        provider=None,
    )
    db_session.add(user)
    await db_session.commit()

    result = await login(
        db_session,
        email="logintest@example.com",
        password="mypassword123",
    )

    assert result.access_token is not None
    assert result.user.email == "logintest@example.com"

    user_id = decode_access_token(result.access_token)
    assert user_id is not None


@pytest.mark.asyncio
async def test_login_wrong_password_fails(db_session: AsyncSession):
    """Test that logging in with wrong password raises InvalidCredentialsError."""
    user = User(
        id=uuid.uuid4(),
        email="wrongpass@example.com",
        name="Wrong Pass User",
        password_hash=hash_password("correctpassword"),
        provider=None,
    )
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        await login(
            db_session,
            email="wrongpass@example.com",
            password="incorrectpassword",
        )


@pytest.mark.asyncio
async def test_login_nonexistent_user_fails(db_session: AsyncSession):
    """Test that logging in with non-existent email raises InvalidCredentialsError."""
    with pytest.raises(InvalidCredentialsError):
        await login(
            db_session,
            email="nonexistent@example.com",
            password="anypassword",
        )
