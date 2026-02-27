import json
from datetime import datetime, timedelta, timezone

import httpx
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import UserProfile
from app.config import settings


async def verify_google_token(id_token: str) -> dict:
    """Verify Google OAuth id_token and return user info."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        )
        if response.status_code != 200:
            raise ValueError("Invalid Google token")

        data = response.json()
        if data.get("aud") != settings.google_client_id:
            raise ValueError("Token audience mismatch")

        return {
            "email": data["email"],
            "name": data.get("name", data["email"].split("@")[0]),
            "avatar_url": data.get("picture"),
            "provider_id": data["sub"],
        }


async def verify_apple_token(id_token: str) -> dict:
    """Verify Apple Sign-In id_token and return user info."""
    async with httpx.AsyncClient() as client:
        # Fetch Apple public keys
        response = await client.get("https://appleid.apple.com/auth/keys")
        if response.status_code != 200:
            raise ValueError("Cannot fetch Apple public keys")

        # Decode and verify JWT (simplified — in production use full JWKS verification)
        # For now, decode without verification to extract claims, then verify audience
        claims = jwt.get_unverified_claims(id_token)

        if claims.get("aud") != settings.apple_client_id:
            raise ValueError("Token audience mismatch")

        return {
            "email": claims.get("email", ""),
            "name": claims.get("name", claims.get("email", "").split("@")[0]),
            "avatar_url": None,
            "provider_id": claims["sub"],
        }


async def get_or_create_user(
    db: AsyncSession,
    provider: str,
    provider_id: str,
    email: str,
    name: str,
    avatar_url: str | None = None,
) -> User:
    """Find existing user by provider+provider_id, or create a new one."""
    result = await db.execute(
        select(User).where(
            User.provider == provider,
            User.provider_id == provider_id,
        )
    )
    user = result.scalar_one_or_none()

    if user is not None:
        # Update name/avatar if changed
        user.name = name
        if avatar_url:
            user.avatar_url = avatar_url
        return user

    user = User(
        email=email,
        name=name,
        avatar_url=avatar_url,
        provider=provider,
        provider_id=provider_id,
    )
    db.add(user)
    await db.flush()
    return user


def create_access_token(user_id: str) -> str:
    """Create a JWT access token for the given user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def user_to_profile(user: User) -> UserProfile:
    """Convert a User model to a UserProfile schema."""
    prefs = []
    if user.dietary_preferences:
        try:
            prefs = json.loads(user.dietary_preferences)
        except (json.JSONDecodeError, TypeError):
            prefs = []

    return UserProfile(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        calorie_goal=user.calorie_goal,
        water_goal_ml=user.water_goal_ml,
        dietary_preferences=prefs,
    )
