"""Users presentation — FastAPI router."""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.config import settings
from app.dependencies import DB, CurrentUser
from app.users.application.user_use_cases import (
    delete_user_account,
    update_dietary_preferences,
    update_goals,
    update_profile,
    upload_avatar,
    user_to_settings,
)
from app.users.presentation import (
    DietaryPreferencesUpdate,
    UserGoalsUpdate,
    UserProfileUpdate,
    UserSettingsResponse,
)

UPLOADS_DIR = Path("uploads/avatars")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserSettingsResponse)
async def get_settings(user: CurrentUser) -> UserSettingsResponse:
    """Get current user settings and preferences."""
    return user_to_settings(user)


@router.patch("/me", response_model=UserSettingsResponse)
async def patch_profile(
    body: UserProfileUpdate, user: CurrentUser, db: DB
) -> UserSettingsResponse:
    """Update user profile (name, avatar)."""
    updated = await update_profile(db, user, body)
    return user_to_settings(updated)


@router.post("/me/avatar", response_model=UserSettingsResponse)
async def upload_user_avatar(
    file: UploadFile, user: CurrentUser, db: DB
) -> UserSettingsResponse:
    """Upload a profile avatar image."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    # Max 5 MB
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB.",
        )

    ext = (
        file.filename.rsplit(".", 1)[-1].lower()
        if file.filename and "." in file.filename
        else "jpg"
    )
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = UPLOADS_DIR / filename
    filepath.write_bytes(image_bytes)

    avatar_url = f"{settings.base_url}/uploads/avatars/{filename}"
    updated = await upload_avatar(db, user, avatar_url)
    return user_to_settings(updated)


@router.delete("/me/avatar", response_model=UserSettingsResponse)
async def delete_user_avatar(user: CurrentUser, db: DB) -> UserSettingsResponse:
    """Remove the user's avatar."""
    updated = await upload_avatar(db, user, None)
    return user_to_settings(updated)


@router.patch("/me/goals", response_model=UserSettingsResponse)
async def patch_goals(
    body: UserGoalsUpdate, user: CurrentUser, db: DB
) -> UserSettingsResponse:
    """Update calorie and water goals."""
    updated = await update_goals(db, user, body)
    return user_to_settings(updated)


@router.patch("/me/diet", response_model=UserSettingsResponse)
async def patch_diet(
    body: DietaryPreferencesUpdate, user: CurrentUser, db: DB
) -> UserSettingsResponse:
    """Update dietary preferences."""
    updated = await update_dietary_preferences(db, user, body)
    return user_to_settings(updated)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(user: CurrentUser, db: DB) -> None:
    """Permanently delete the authenticated user account."""
    await delete_user_account(db, user)
