"""Auth presentation — Pydantic request/response schemas."""

from pydantic import BaseModel, EmailStr, Field


# ── OAuth ────────────────────────────────────


class OAuthRequest(BaseModel):
    token: str
    provider: str  # "google" | "apple"


# ── Email/Password ───────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Responses ────────────────────────────────


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
