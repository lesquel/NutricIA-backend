import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.application.email_auth import register
from app.auth.domain import EmailAlreadyExistsError
from app.shared.infrastructure.security import decode_access_token


@pytest.mark.asyncio
async def test_register_creates_user_successfully(db_session: AsyncSession):
    """Test that registering a new user creates the user and returns a valid token."""
    result = await register(
        db_session,
        email="newuser@example.com",
        password="securepassword123",
        name="New User",
    )

    assert result.access_token is not None
    assert result.user.email == "newuser@example.com"
    assert result.user.name == "New User"

    user_id = decode_access_token(result.access_token)
    assert user_id is not None


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(db_session: AsyncSession):
    """Test that registering with an existing email raises EmailAlreadyExistsError."""
    from app.auth.infrastructure.repository import hash_password
    from app.auth.infrastructure.models import User
    import uuid

    existing_user = User(
        id=uuid.uuid4(),
        email="existing@example.com",
        name="Existing User",
        password_hash=hash_password("password123"),
        provider=None,
    )
    db_session.add(existing_user)
    await db_session.commit()

    with pytest.raises(EmailAlreadyExistsError):
        await register(
            db_session,
            email="existing@example.com",
            password="newpassword123",
            name="Another User",
        )


@pytest.mark.asyncio
async def test_register_invalid_email_fails(db_session: AsyncSession):
    """Test that registering with an invalid email format fails at Pydantic validation."""
    from app.auth.presentation import RegisterRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="not-an-email",
            password="password123",
            name="Invalid Email User",
        )


@pytest.mark.asyncio
async def test_register_short_password_fails(db_session: AsyncSession):
    """Test that registering with a short password fails at Pydantic validation."""
    from app.auth.presentation import RegisterRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="user@example.com",
            password="123",
            name="Short Password User",
        )
