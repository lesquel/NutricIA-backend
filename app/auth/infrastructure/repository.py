"""Auth infrastructure — User repository."""

import uuid
from datetime import datetime

import bcrypt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import RefreshToken, TokenBlocklist, User


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


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Get a user by their UUID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ── Refresh Tokens ─────────────────────────────


async def create_refresh_token_record(
    db: AsyncSession,
    user_id: str,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    """Persist a new refresh token record."""
    record = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(record)
    await db.flush()
    return record


async def get_refresh_token_by_hash(
    db: AsyncSession, token_hash: str
) -> RefreshToken | None:
    """Look up a refresh token by its SHA-256 hash."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def delete_refresh_token(db: AsyncSession, token_id: uuid.UUID) -> None:
    """Delete a single refresh token by ID."""
    await db.execute(delete(RefreshToken).where(RefreshToken.id == token_id))


async def delete_all_user_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    """Delete all refresh tokens belonging to a user."""
    await db.execute(
        delete(RefreshToken).where(RefreshToken.user_id == uuid.UUID(user_id))
    )


# ── Token Blocklist ────────────────────────────


async def add_to_blocklist(
    db: AsyncSession, jti: str, expires_at: datetime
) -> None:
    """Add a JWT id to the blocklist (revoke an access token)."""
    entry = TokenBlocklist(
        id=uuid.uuid4(),
        jti=jti,
        expires_at=expires_at,
    )
    db.add(entry)
    await db.flush()


async def is_token_blocked(db: AsyncSession, jti: str) -> bool:
    """Check if a JWT id has been revoked."""
    result = await db.execute(
        select(TokenBlocklist.id).where(TokenBlocklist.jti == jti)
    )
    return result.scalar_one_or_none() is not None
