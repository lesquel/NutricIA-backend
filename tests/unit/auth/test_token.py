import pytest

from app.shared.infrastructure.security import create_access_token, decode_access_token
from app.shared.domain import UnauthorizedError


def test_valid_token_decodes_correctly():
    """Test that a valid token decodes to the correct user ID."""
    user_id = "test-user-id-12345"
    token = create_access_token(user_id)

    decoded_user_id = decode_access_token(token)

    assert decoded_user_id == user_id


def test_expired_token_raises_error(expired_token: str):
    """Test that an expired token raises UnauthorizedError."""
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(expired_token)

    assert "Could not validate credentials" in str(exc_info.value.message)


def test_invalid_token_raises_error():
    """Test that an invalid token raises UnauthorizedError."""
    invalid_token = "this.is.not.a.valid.token"

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(invalid_token)

    assert "Could not validate credentials" in str(exc_info.value.message)


def test_token_with_wrong_secret_raises_error():
    """Test that a token encoded with wrong secret raises UnauthorizedError."""
    from jose import jwt
    from datetime import datetime, timedelta, timezone

    user_id = "test-user-id"
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        "iat": datetime.now(timezone.utc),
    }
    wrong_secret_token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

    with pytest.raises(UnauthorizedError):
        decode_access_token(wrong_secret_token)
