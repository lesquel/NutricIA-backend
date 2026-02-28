"""Users presentation — FastAPI router."""

from fastapi import APIRouter

from app.dependencies import DB, CurrentUser
from app.users.application.user_use_cases import (
    update_dietary_preferences,
    update_goals,
    update_profile,
    user_to_settings,
)
from app.users.presentation import (
    DietaryPreferencesUpdate,
    UserGoalsUpdate,
    UserProfileUpdate,
    UserSettingsResponse,
)

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
