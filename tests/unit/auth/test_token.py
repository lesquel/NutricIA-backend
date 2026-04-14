import pytest

from app.shared.infrastructure.security import create_access_token, decode_access_token
from app.shared.domain import UnauthorizedError


def test_valid_token_decodes_correctly():
    """Test that a valid token decodes to the correct user ID."""
    user_id = "test-user-id-12345"
    token = create_access_token(user_id)

    payload = decode_access_token(token)

    assert payload.user_id == user_id


def test_decode_access_token_includes_jti():
    """Test that decoded token includes a jti claim."""
    user_id = "test-user-id-12345"
    token = create_access_token(user_id)

    payload = decode_access_token(token)

    assert payload.jti is not None
    assert isinstance(payload.jti, str)
    assert len(payload.jti) > 0


def test_create_access_token_includes_jti_in_jwt():
    """Test that the raw JWT payload contains a jti claim."""
    from jose import jwt
    from app.config import settings

    user_id = "test-user-id-jti"
    token = create_access_token(user_id)

    raw_payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    assert "jti" in raw_payload
    assert isinstance(raw_payload["jti"], str)
    assert len(raw_payload["jti"]) == 36  # UUID format


def test_each_token_gets_unique_jti():
    """Test that each generated token has a unique jti."""
    user_id = "test-user-id"
    token1 = create_access_token(user_id)
    token2 = create_access_token(user_id)

    payload1 = decode_access_token(token1)
    payload2 = decode_access_token(token2)

    assert payload1.jti != payload2.jti


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
