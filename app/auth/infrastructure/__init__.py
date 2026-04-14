"""Auth infrastructure — OAuth provider verification."""

import time
from typing import Any

import httpx
from jose import jwk, jwt as jose_jwt
from jose.exceptions import JWTError, JWTClaimsError, ExpiredSignatureError

from app.config import settings
from app.auth.domain import InvalidTokenError

# ---------------------------------------------------------------------------
# Apple JWKS cache (24h TTL)
# ---------------------------------------------------------------------------

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"
_JWKS_CACHE_TTL = 86400  # 24 hours in seconds


class _AppleJWKSCache:
    """Simple in-memory cache for Apple JWKS keys."""

    def __init__(self) -> None:
        self._keys: list[dict[str, Any]] = []
        self._fetched_at: float = 0.0

    def get(self) -> list[dict[str, Any]] | None:
        if self._keys and (time.time() - self._fetched_at) < _JWKS_CACHE_TTL:
            return self._keys
        return None

    def set(self, keys: list[dict[str, Any]]) -> None:
        self._keys = keys
        self._fetched_at = time.time()

    def clear(self) -> None:
        self._keys = []
        self._fetched_at = 0.0


_apple_jwks_cache = _AppleJWKSCache()


async def _fetch_apple_jwks() -> list[dict[str, Any]]:
    """Fetch JWKS from Apple's endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get(APPLE_JWKS_URL)
        if response.status_code != 200:
            raise InvalidTokenError("Cannot fetch Apple public keys")
        return response.json()["keys"]


async def _get_apple_jwks() -> list[dict[str, Any]]:
    """Return Apple JWKS keys, using cache when available."""
    cached = _apple_jwks_cache.get()
    if cached is not None:
        return cached
    keys = await _fetch_apple_jwks()
    _apple_jwks_cache.set(keys)
    return keys


async def verify_google_token(id_token: str) -> dict:
    """Verify Google OAuth id_token and return user info."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        )
        if response.status_code != 200:
            raise InvalidTokenError("Invalid Google token")

        data = response.json()
        if data.get("aud") != settings.google_client_id:
            raise InvalidTokenError("Token audience mismatch")

        return {
            "email": data["email"],
            "name": data.get("name", data["email"].split("@")[0]),
            "avatar_url": data.get("picture"),
            "provider_id": data["sub"],
        }


async def verify_apple_token(id_token: str) -> dict:
    """Verify Apple Sign-In id_token using JWKS RS256 verification.

    Fetches Apple's JWKS public keys, matches the kid from the token header,
    constructs the RSA key, and verifies signature + claims (aud, iss, exp).
    """
    try:
        headers = jose_jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise InvalidTokenError(f"Malformed token header: {exc}") from exc

    kid = headers.get("kid")
    if not kid:
        raise InvalidTokenError("Token header missing kid")

    keys = await _get_apple_jwks()

    # Find the key matching the kid
    matching_key = None
    for key_data in keys:
        if key_data.get("kid") == kid:
            matching_key = key_data
            break

    if matching_key is None:
        raise InvalidTokenError("Token kid not found in Apple JWKS")

    try:
        public_key = jwk.construct(matching_key, algorithm="RS256")
    except Exception as exc:
        raise InvalidTokenError(f"Failed to construct public key: {exc}") from exc

    try:
        claims = jose_jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=settings.apple_client_id,
            issuer=APPLE_ISSUER,
        )
    except ExpiredSignatureError as exc:
        raise InvalidTokenError("Apple token has expired") from exc
    except JWTClaimsError as exc:
        raise InvalidTokenError(f"Token claims validation failed: {exc}") from exc
    except JWTError as exc:
        raise InvalidTokenError(f"Token verification failed: {exc}") from exc

    return {
        "email": claims.get("email", ""),
        "name": claims.get("name", claims.get("email", "").split("@")[0]),
        "avatar_url": None,
        "provider_id": claims["sub"],
    }
