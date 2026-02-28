"""Meals presentation — FastAPI router."""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.dependencies import DB, CurrentUser
from app.meals.domain import FoodAnalysisError, AIProviderError
from app.meals.application.scan_food import scan_food
from app.meals.application.meal_crud import (
    save_meal,
    list_meals,
    get_meal,
    remove_meal,
    meal_to_response,
)
from app.meals.presentation import (
    ScanResult,
    MealCreate,
    MealResponse,
    MealListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meals", tags=["meals"])


@router.post("/scan", response_model=ScanResult)
async def scan_meal(file: UploadFile, user: CurrentUser) -> ScanResult:
    """Upload a food photo for AI analysis. Returns nutritional data (not saved yet)."""
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

    try:
        return await scan_food(image_bytes, file.content_type)
    except FoodAnalysisError as e:
        detail_map = {
            "not_food": "The image doesn't appear to contain food. Please try again with a food photo.",
            "blurry": "The image is too blurry to analyze. Please take a clearer photo.",
        }
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail_map.get(e.error_type, f"Analysis failed: {e.error_type}"),
        )
    except AIProviderError as e:
        if e.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=e.detail,
            )
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_ENTITY if 400 <= e.status_code < 500 else status.HTTP_502_BAD_GATEWAY),
            detail=e.detail,
        )
    except Exception:
        logger.exception("Unexpected error during meal scan")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during analysis. Please try again.",
        )


@router.post("", response_model=MealResponse, status_code=status.HTTP_201_CREATED)
async def add_meal(body: MealCreate, user: CurrentUser, db: DB) -> MealResponse:
    """Confirm and save a scanned or manually entered meal."""
    meal = await save_meal(db, user.id, body)
    return meal_to_response(meal)


@router.get("", response_model=MealListResponse)
async def list_daily_meals(
    user: CurrentUser,
    db: DB,
    target_date: date | None = None,
) -> MealListResponse:
    """List meals for a given date (defaults to today)."""
    if target_date is None:
        target_date = date.today()

    meals = await list_meals(db, user.id, target_date)
    meal_responses = [meal_to_response(m) for m in meals]

    return MealListResponse(
        meals=meal_responses,
        total_calories=sum(m.calories for m in meals),
        total_protein=sum(m.protein_g for m in meals),
        total_carbs=sum(m.carbs_g for m in meals),
        total_fat=sum(m.fat_g for m in meals),
    )


@router.get("/{meal_id}", response_model=MealResponse)
async def get_single_meal(meal_id: str, user: CurrentUser, db: DB) -> MealResponse:
    """Get a single meal by ID."""
    meal = await get_meal(db, user.id, meal_id)
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )
    return meal_to_response(meal)


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(meal_id: str, user: CurrentUser, db: DB) -> None:
    """Delete a meal."""
    meal = await get_meal(db, user.id, meal_id)
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )
    await remove_meal(db, meal)
