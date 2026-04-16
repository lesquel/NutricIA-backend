"""Auth infrastructure — User repository."""

import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import User


# ── Password helpers ───────────────────────────


def hash_password(plain: str) -> str:
    """Return bcrypt hash for a plaintext password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── OAuth (existing) ───────────────────────────


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

    # Check if email already exists (user may have registered with password)
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        # Link OAuth to existing email account
        existing.provider = provider
        existing.provider_id = provider_id
        existing.name = name
        if avatar_url:
            existing.avatar_url = avatar_url
        return existing

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


# ── Email/Password ─────────────────────────────


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Find a user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_email_user(
    db: AsyncSession,
    email: str,
    name: str,
    password: str,
) -> User:
    """Create a new user with email + hashed password."""
    user = User(
        email=email,
        name=name,
        password_hash=hash_password(password),
        provider=None,
        provider_id=None,
    )
    db.add(user)
    await db.flush()
    return user


# ── Generic ────────────────────────────────────


async def get_user_by_id(db: AsyncSession, user_id: str | uuid.UUID) -> User | None:
    """Get a user by their UUID.

    Accepts either a UUID object or a string representation. SQLite's
    UUID type processor requires a UUID object (it reads `.hex`), so
    string inputs are normalized here before the query.
    """
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
