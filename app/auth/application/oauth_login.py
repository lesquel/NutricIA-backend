"""Use case: OAuth Login.

Verifies an OAuth token, upserts the user, and returns a JWT.
"""

import json
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.domain import InvalidTokenError, OAuthProvider
from app.auth.infrastructure import verify_google_token, verify_apple_token
from app.auth.infrastructure.repository import get_or_create_user
from app.auth.presentation import TokenResponse, UserProfile
from app.shared.infrastructure.security import create_access_token

if TYPE_CHECKING:
    from app.auth.infrastructure.models import User


async def oauth_login(
    db: AsyncSession,
    id_token: str,
    provider: str,
) -> TokenResponse:
    """Authenticate via OAuth and return JWT + user profile."""
    if provider == OAuthProvider.GOOGLE:
        user_info = await verify_google_token(id_token)
    elif provider == OAuthProvider.APPLE:
        user_info = await verify_apple_token(id_token)
    else:
        raise InvalidTokenError(f"Unsupported provider: {provider}")

    user = await get_or_create_user(
        db=db,
        provider=provider,
        provider_id=user_info["provider_id"],
        email=user_info["email"],
        name=user_info["name"],
        avatar_url=user_info.get("avatar_url"),
    )

    token = create_access_token(str(user.id))
    profile = user_to_profile(user)

    return TokenResponse(access_token=token, user=profile)


def user_to_profile(user: "User") -> UserProfile:
    """Convert a User model to a UserProfile schema."""
    prefs: list[str] = []
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
