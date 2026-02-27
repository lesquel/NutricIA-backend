import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.users.schemas import (
    DietaryPreferencesUpdate,
    UserGoalsUpdate,
    UserProfileUpdate,
    UserSettingsResponse,
)


async def update_profile(
    db: AsyncSession,
    user: User,
    data: UserProfileUpdate,
) -> User:
    if data.name is not None:
        user.name = data.name
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url
    await db.flush()
    return user


async def update_goals(
    db: AsyncSession,
    user: User,
    data: UserGoalsUpdate,
) -> User:
    if data.calorie_goal is not None:
        user.calorie_goal = data.calorie_goal
    if data.water_goal_ml is not None:
        user.water_goal_ml = data.water_goal_ml
    await db.flush()
    return user


async def update_dietary_preferences(
    db: AsyncSession,
    user: User,
    data: DietaryPreferencesUpdate,
) -> User:
    user.dietary_preferences = json.dumps(data.preferences)
    await db.flush()
    return user


def user_to_settings(user: User) -> UserSettingsResponse:
    prefs: list[str] = []
    if user.dietary_preferences:
        try:
            prefs = json.loads(user.dietary_preferences)
        except (json.JSONDecodeError, TypeError):
            prefs = []

    return UserSettingsResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        calorie_goal=user.calorie_goal,
        water_goal_ml=user.water_goal_ml,
        dietary_preferences=prefs,
    )
