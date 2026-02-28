"""JWT security utilities — encode/decode tokens."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings
from app.shared.domain import UnauthorizedError


def create_access_token(user_id: str) -> str:
    """Create a JWT access token for the given user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Decode a JWT token and return the user_id (sub claim).

    Raises UnauthorizedError if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise UnauthorizedError("Invalid token payload")
        return user_id
    except JWTError:
        raise UnauthorizedError("Could not validate credentials")
