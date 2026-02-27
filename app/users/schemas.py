from pydantic import BaseModel


class UserGoalsUpdate(BaseModel):
    calorie_goal: int | None = None
    water_goal_ml: int | None = None


class DietaryPreferencesUpdate(BaseModel):
    preferences: list[str]  # ["Vegan", "Low Sugar", ...]


class UserProfileUpdate(BaseModel):
    name: str | None = None
    avatar_url: str | None = None


class UserSettingsResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None
    calorie_goal: int
    water_goal_ml: int
    dietary_preferences: list[str]

    model_config = {"from_attributes": True}
