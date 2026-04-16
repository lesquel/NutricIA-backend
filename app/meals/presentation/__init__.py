"""Meals presentation — Pydantic request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ScanResult(BaseModel):
    """Result returned by AI food analysis."""

    name: str
    ingredients: list[str] = []
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    confidence: float = Field(ge=0.0, le=1.0)
    tags: list[str] = []


class MealCreate(BaseModel):
    name: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_type: str = "snack"  # breakfast | lunch | snack | dinner
    confidence_score: float = 0.0
    tags: list[str] = []
    image_url: str | None = None
    logged_at: datetime | None = None


class MealResponse(BaseModel):
    id: str
    name: str
    image_url: str | None = None
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_type: str
    confidence_score: float
    tags: list[str] = []
    logged_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class MealListResponse(BaseModel):
    meals: list[MealResponse]
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float


class MealImageUploadResponse(BaseModel):
    image_url: str


class MealCalendarResponse(BaseModel):
    month: str
    registered_dates: list[str]


class MealUpdate(BaseModel):
    """Partial update payload for a saved meal."""

    name: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    meal_type: str | None = None
    image_url: str | None = None
