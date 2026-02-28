"""Auth infrastructure — User repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import User


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


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Get a user by their UUID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
