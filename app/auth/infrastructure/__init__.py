"""Auth infrastructure — OAuth provider verification."""

import httpx

from app.config import settings
from app.auth.domain import InvalidTokenError
from app.auth.infrastructure.apple_jwks import verify_apple_token as _verify_apple_jwks


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
    """Verify Apple Sign-In id_token with full JWKS signature verification.

    Validates signature, issuer, audience, and expiry against Apple's public keys.
    """
    return await _verify_apple_jwks(id_token)
