"""JWT security utilities — encode/decode tokens."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import cast

from jose import JWTError, jwt

from app.config import settings
from app.shared.domain import UnauthorizedError


@dataclass(frozen=True)
class TokenPayload:
    """Decoded JWT payload."""

    user_id: str
    jti: str | None


def create_access_token(user_id: str) -> str:
    """Create a JWT access token for the given user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return cast(
        str,
        jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm),
    )


def decode_access_token(token: str) -> TokenPayload:
    """Decode a JWT token and return a TokenPayload with user_id and jti.

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
        jti: str | None = payload.get("jti")
        return TokenPayload(user_id=user_id, jti=jti)
    except JWTError:
        raise UnauthorizedError("Could not validate credentials")


# ── Refresh tokens ───────────────────────────


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Create an opaque refresh token and its SHA-256 hash.

    Returns (opaque_token, token_hash).
    """
    opaque_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(opaque_token.encode()).hexdigest()
    return opaque_token, token_hash


def verify_refresh_token_hash(token: str, stored_hash: str) -> bool:
    """Check whether an opaque token matches its stored SHA-256 hash."""
    return hashlib.sha256(token.encode()).hexdigest() == stored_hash
