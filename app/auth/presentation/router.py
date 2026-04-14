"""Auth presentation — FastAPI router."""

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status

from app.auth.application.oauth_login import oauth_login, user_to_profile
from app.auth.application.email_auth import register, login
from app.auth.domain import (
    InvalidTokenError,
    InvalidCredentialsError,
    EmailAlreadyExistsError,
)
from app.auth.infrastructure.repository import (
    add_to_blocklist,
    create_refresh_token_record,
    delete_all_user_refresh_tokens,
    delete_refresh_token,
    get_refresh_token_by_hash,
)
from app.auth.presentation import (
    OAuthRequest,
    RefreshRequest,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserProfile,
)
from app.config import Settings
from app.dependencies import DB, CurrentUser
from app.shared.infrastructure.rate_limit import limiter
from app.shared.infrastructure.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Email/Password ───────────────────────────


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
async def do_register(request: Request, body: RegisterRequest, db: DB) -> TokenResponse:
    """Register a new account with email and password."""
    try:
        return await register(db, body.email, body.password, body.name)
    except EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def do_login(request: Request, body: LoginRequest, db: DB) -> TokenResponse:
    """Log in with email and password."""
    try:
        return await login(db, body.email, body.password)
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
        )


# ── OAuth ────────────────────────────────────


@router.post("/oauth", response_model=TokenResponse)
@limiter.limit("5/minute")
async def do_oauth_login(request: Request, body: OAuthRequest, db: DB) -> TokenResponse:
    """Authenticate with Google or Apple OAuth token."""
    try:
        return await oauth_login(db, body.token, body.provider)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


# ── Current User ─────────────────────────────


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def do_refresh(request: Request, body: RefreshRequest, db: DB) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh pair (rotation)."""
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    record = await get_refresh_token_by_hash(db, token_hash)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Compare timezone-aware (SQLite may strip tz info)
    now = datetime.now(timezone.utc)
    expires = (
        record.expires_at.replace(tzinfo=timezone.utc)
        if record.expires_at.tzinfo is None
        else record.expires_at
    )
    if expires < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Delete old refresh token (rotation)
    await delete_refresh_token(db, record.id)

    # Issue new pair
    user_id = str(record.user_id)
    new_access = create_access_token(user_id)
    raw_refresh, new_hash = create_refresh_token(user_id)

    settings = Settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_expire_days
    )
    await create_refresh_token_record(db, record.user_id, new_hash, expires_at)

    # Build profile for response
    from app.auth.infrastructure.repository import get_user_by_id

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    profile = user_to_profile(user)
    return TokenResponse(
        access_token=new_access, refresh_token=raw_refresh, user=profile
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def do_logout(
    request: Request,
    user: CurrentUser,
    db: DB,
) -> None:
    """Log out: block current access token and revoke all refresh tokens."""
    # Block the access token via its jti
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    try:
        payload = decode_access_token(token)
        if payload.jti is not None:
            settings_obj = Settings()
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=settings_obj.jwt_expire_minutes
            )
            await add_to_blocklist(db, payload.jti, expires_at)
    except Exception:
        pass  # Token already validated by CurrentUser dependency

    # Revoke all refresh tokens for this user
    await delete_all_user_refresh_tokens(db, user.id)


@router.get("/me", response_model=UserProfile)
async def get_me(user: CurrentUser) -> UserProfile:
    """Get current authenticated user profile."""
    return user_to_profile(user)
