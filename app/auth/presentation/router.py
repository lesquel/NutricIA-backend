"""Auth presentation — FastAPI router."""

from fastapi import APIRouter, HTTPException, Request, status

from app.auth.application.oauth_login import oauth_login, user_to_profile
from app.auth.application.email_auth import register, login
from app.auth.application.request_password_reset_uc import request_password_reset
from app.auth.application.reset_password_uc import reset_password
from app.auth.domain import (
    InvalidTokenError,
    InvalidCredentialsError,
    EmailAlreadyExistsError,
    TokenExpiredError,
    TokenAlreadyUsedError,
    TokenNotFoundError,
)
from app.auth.presentation import (
    OAuthRequest,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserProfile,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.auth.infrastructure.rate_limiter import check_rate_limit
from app.dependencies import DB, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_email_adapter():
    """Return the appropriate email adapter based on settings."""
    from app.config import settings
    from app.notifications.infrastructure.console_adapter import ConsoleEmailAdapter
    from app.notifications.infrastructure.smtp_adapter import SmtpEmailAdapter

    if settings.smtp_host:
        return SmtpEmailAdapter()
    return ConsoleEmailAdapter()


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


# ── Forgot Password ──────────────────────────


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def do_forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: DB,
) -> ForgotPasswordResponse:
    """Request a password reset link. Always returns 200 (no user enumeration)."""
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"forgot:{client_ip}"

    if not check_rate_limit(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before requesting another reset.",
        )

    email_adapter = _get_email_adapter()
    await request_password_reset(db, body.email, email_adapter)
    return ForgotPasswordResponse()


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def do_reset_password(
    body: ResetPasswordRequest,
    db: DB,
) -> ResetPasswordResponse:
    """Reset password using a valid reset token."""
    try:
        await reset_password(db, body.token, body.new_password)
        return ResetPasswordResponse()
    except TokenNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except TokenAlreadyUsedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
