from fastapi import APIRouter, HTTPException, status

from app.auth.schemas import OAuthRequest, TokenResponse
from app.auth.service import (
    create_access_token,
    get_or_create_user,
    user_to_profile,
    verify_apple_token,
    verify_google_token,
)
from app.dependencies import DB, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/oauth", response_model=TokenResponse)
async def oauth_login(body: OAuthRequest, db: DB) -> TokenResponse:
    """Authenticate with Google or Apple OAuth token."""
    try:
        if body.provider == "google":
            user_info = await verify_google_token(body.id_token)
        elif body.provider == "apple":
            user_info = await verify_apple_token(body.id_token)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {body.provider}",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    user = await get_or_create_user(
        db=db,
        provider=body.provider,
        provider_id=user_info["provider_id"],
        email=user_info["email"],
        name=user_info["name"],
        avatar_url=user_info.get("avatar_url"),
    )

    token = create_access_token(str(user.id))
    profile = user_to_profile(user)

    return TokenResponse(access_token=token, user=profile)


@router.get("/me", response_model=TokenResponse.model_fields["user"].annotation)
async def get_me(user: CurrentUser):
    """Get current authenticated user profile."""
    return user_to_profile(user)
