"""Auth infrastructure — Apple JWKS verification with in-memory TTL cache."""

import asyncio
import logging
import time
from typing import Any

import httpx
from jose import jwt as jose_jwt
from jose import jwk as jose_jwk
from jose.exceptions import JWTError

from app.auth.domain import InvalidTokenError
from app.config import settings

logger = logging.getLogger("nutricia.auth")

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"
_CACHE_TTL_SECONDS = 3600  # 1 hour (Apple key rotation safety)

# In-memory JWKS cache: {keys: list, fetched_at: float}
_jwks_cache: dict[str, Any] = {}
_cache_lock = asyncio.Lock()


async def _fetch_jwks() -> list[dict[str, Any]]:
    """Fetch Apple JWKS from Apple's endpoint."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(APPLE_JWKS_URL)
        if response.status_code != 200:
            raise InvalidTokenError("Apple identity service unavailable")
        data: dict[str, Any] = response.json()
        keys = data.get("keys", [])
        return list(keys) if keys else []


async def _get_jwks() -> list[dict[str, Any]]:
    """Return cached JWKS or fetch fresh if TTL expired."""
    async with _cache_lock:
        now = time.monotonic()
        cached_keys = _jwks_cache.get("keys")
        if (
            cached_keys is not None
            and now - _jwks_cache.get("fetched_at", 0) < _CACHE_TTL_SECONDS
        ):
            return list(cached_keys)

        try:
            keys = await _fetch_jwks()
        except httpx.RequestError as exc:
            raise InvalidTokenError("Apple identity service unavailable") from exc

        _jwks_cache["keys"] = keys
        _jwks_cache["fetched_at"] = now
        return keys


def _invalidate_cache() -> None:
    """Invalidate the in-memory JWKS cache (for testing)."""
    _jwks_cache.clear()


async def verify_apple_token(id_token: str) -> dict:
    """Verify an Apple Sign-In JWT against Apple's public JWKS.

    Validates: signature, issuer, audience, expiry.

    Returns user info dict on success.
    Raises InvalidTokenError on any verification failure.
    """
    # Decode header without verification to get kid
    try:
        header = jose_jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise InvalidTokenError("Invalid Apple token format") from exc

    kid = header.get("kid")
    alg = header.get("alg", "RS256")

    jwks = await _get_jwks()

    # Find the matching key
    matching_key = None
    for key_data in jwks:
        if key_data.get("kid") == kid:
            matching_key = key_data
            break

    if matching_key is None:
        raise InvalidTokenError("Apple signing key not found")

    # Construct the public key
    try:
        public_key = jose_jwk.construct(matching_key, algorithm=alg)
    except Exception as exc:
        raise InvalidTokenError("Failed to construct Apple signing key") from exc

    # Verify and decode the token
    try:
        claims = jose_jwt.decode(
            id_token,
            public_key,
            algorithms=[alg],
            audience=settings.apple_client_id,
            issuer=APPLE_ISSUER,
            options={"verify_exp": True},
        )
    except JWTError as exc:
        error_msg = str(exc).lower()
        if "expired" in error_msg or "exp" in error_msg:
            raise InvalidTokenError("Apple token expired") from exc
        if "audience" in error_msg or "aud" in error_msg:
            raise InvalidTokenError("Apple token audience mismatch") from exc
        if "issuer" in error_msg or "iss" in error_msg:
            raise InvalidTokenError("Apple token issuer mismatch") from exc
        raise InvalidTokenError("Invalid Apple token signature") from exc

    return {
        "email": claims.get("email", ""),
        "name": claims.get("name", claims.get("email", "").split("@")[0]),
        "avatar_url": None,
        "provider_id": claims["sub"],
    }
