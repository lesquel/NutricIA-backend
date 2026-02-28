"""Auth infrastructure — OAuth provider verification."""

import httpx
from jose import jwt as jose_jwt

from app.config import settings
from app.auth.domain import InvalidTokenError


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
    """Verify Apple Sign-In id_token and return user info.

    NOTE: Uses simplified verification. For production, implement full JWKS
    signature verification with Apple's public keys.
    """
    async with httpx.AsyncClient() as client:
        # Fetch Apple public keys
        response = await client.get("https://appleid.apple.com/auth/keys")
        if response.status_code != 200:
            raise InvalidTokenError("Cannot fetch Apple public keys")

        # TODO: Implement full JWKS verification
        # For now, decode without verification to extract claims
        claims = jose_jwt.get_unverified_claims(id_token)

        if claims.get("aud") != settings.apple_client_id:
            raise InvalidTokenError("Token audience mismatch")

        return {
            "email": claims.get("email", ""),
            "name": claims.get("name", claims.get("email", "").split("@")[0]),
            "avatar_url": None,
            "provider_id": claims["sub"],
        }
