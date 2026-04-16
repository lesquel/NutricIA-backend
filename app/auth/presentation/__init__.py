"""Auth presentation — Pydantic request/response schemas."""

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── OAuth ────────────────────────────────────


class OAuthRequest(BaseModel):
    id_token: str
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


# ── Forgot Password ──────────────────────────


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str = "If an account with that email exists, a reset link has been sent."


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("token")
    @classmethod
    def token_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("token must not be empty")
        return v


class ResetPasswordResponse(BaseModel):
    message: str = "Password reset successfully."
