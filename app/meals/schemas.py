from datetime import datetime

from pydantic import BaseModel, Field


class MacroBreakdown(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0


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


class ScanError(BaseModel):
    error: str  # "not_food" | "blurry" | "unknown"


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
