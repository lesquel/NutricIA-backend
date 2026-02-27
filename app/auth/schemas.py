from pydantic import BaseModel, EmailStr


class OAuthRequest(BaseModel):
    id_token: str
    provider: str  # "google" | "apple"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserProfile"


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None = None
    calorie_goal: int = 2100
    water_goal_ml: int = 2500
    dietary_preferences: list[str] = []

    model_config = {"from_attributes": True}


# Rebuild model to resolve forward reference
TokenResponse.model_rebuild()
