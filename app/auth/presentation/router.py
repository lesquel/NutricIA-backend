"""Auth presentation — FastAPI router."""

from fastapi import APIRouter, HTTPException, status

from app.auth.application.oauth_login import oauth_login, user_to_profile
from app.auth.domain import InvalidTokenError
from app.auth.presentation import OAuthRequest, TokenResponse, UserProfile
from app.dependencies import DB, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.get("/me", response_model=UserProfile)
async def get_me(user: CurrentUser) -> UserProfile:
    """Get current authenticated user profile."""
    return user_to_profile(user)
