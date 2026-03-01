"""Auth presentation — FastAPI router."""

from fastapi import APIRouter, HTTPException, status

from app.auth.application.oauth_login import oauth_login, user_to_profile
from app.auth.application.email_auth import register, login
from app.auth.domain import (
    InvalidTokenError,
    InvalidCredentialsError,
    EmailAlreadyExistsError,
)
from app.auth.presentation import (
    OAuthRequest,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserProfile,
)
from app.dependencies import DB, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Email/Password ───────────────────────────


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def do_register(body: RegisterRequest, db: DB) -> TokenResponse:
    """Register a new account with email and password."""
    try:
        return await register(db, body.email, body.password, body.name)
    except EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )


@router.post("/login", response_model=TokenResponse)
async def do_login(body: LoginRequest, db: DB) -> TokenResponse:
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
async def do_oauth_login(body: OAuthRequest, db: DB) -> TokenResponse:
    """Authenticate with Google or Apple OAuth token."""
    try:
        return await oauth_login(db, body.id_token, body.provider)
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


@router.get("/me", response_model=UserProfile)
async def get_me(user: CurrentUser) -> UserProfile:
    """Get current authenticated user profile."""
    return user_to_profile(user)
