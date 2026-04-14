"""Meals presentation — FastAPI router."""

import logging
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, status

from app.dependencies import DB, CurrentUser
from app.meals.domain import FoodAnalysisError, AIProviderError
from app.meals.application.scan_food import scan_food
from app.meals.application.meal_crud import (
    save_meal,
    list_meals,
    get_meal,
    remove_meal,
    meal_to_response,
    get_meal_dates_in_month,
)
from app.meals.presentation import (
    ScanResult,
    MealCreate,
    MealResponse,
    MealListResponse,
    MealImageUploadResponse,
    MealCalendarResponse,
)
from app.shared.infrastructure.rate_limit import limiter

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/meals", tags=["meals"])


@router.post("/scan", response_model=ScanResult)
@limiter.limit("10/minute")
async def scan_meal(request: Request, file: UploadFile, user: CurrentUser) -> ScanResult:
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
    if len(image_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 5MB.",
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
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
                if 400 <= e.status_code < 500
                else status.HTTP_502_BAD_GATEWAY
            ),
            detail=e.detail,
        )
    except Exception:
        logger.exception("Unexpected error during meal scan")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during analysis. Please try again.",
        )


@router.post("/upload-image", response_model=MealImageUploadResponse)
@limiter.limit("20/minute")
async def upload_meal_image(
    request: Request, file: UploadFile, user: CurrentUser
) -> MealImageUploadResponse:
    """Upload meal image and return a public URL to persist on the meal record."""
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
    if len(image_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 5MB.",
        )

    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    relative_dir = Path("uploads") / "meals" / str(user.id)
    absolute_dir = Path.cwd() / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{suffix}"
    file_path = absolute_dir / filename
    file_path.write_bytes(image_bytes)

    # Store relative path — resolved to absolute URL via request.base_url
    image_url = f"/{relative_dir.as_posix()}/{filename}"
    return MealImageUploadResponse(image_url=image_url)


@router.post("", response_model=MealResponse, status_code=status.HTTP_201_CREATED)
async def add_meal(
    body: MealCreate, user: CurrentUser, db: DB, request: Request
) -> MealResponse:
    """Confirm and save a scanned or manually entered meal."""
    meal = await save_meal(db, user.id, body)
    return meal_to_response(meal, base_url=str(request.base_url))


@router.get("", response_model=MealListResponse)
async def list_daily_meals(
    user: CurrentUser,
    db: DB,
    request: Request,
    target_date: date | None = None,
) -> MealListResponse:
    """List meals for a given date (defaults to today)."""
    if target_date is None:
        target_date = date.today()

    meals = await list_meals(db, user.id, target_date)
    base = str(request.base_url)
    meal_responses = [meal_to_response(m, base_url=base) for m in meals]

    return MealListResponse(
        meals=meal_responses,
        total_calories=sum(m.calories for m in meals),
        total_protein=sum(m.protein_g for m in meals),
        total_carbs=sum(m.carbs_g for m in meals),
        total_fat=sum(m.fat_g for m in meals),
    )


@router.get("/calendar", response_model=MealCalendarResponse)
async def get_meal_calendar(
    user: CurrentUser,
    db: DB,
    month: str,
) -> MealCalendarResponse:
    """Get all dates in a month that have at least one registered meal.

    Query format: month=YYYY-MM
    """
    try:
        year, month_num = month.split("-")
        month_start = date(int(year), int(month_num), 1)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid month format. Use YYYY-MM",
        )

    dates = await get_meal_dates_in_month(db, user.id, month_start)
    return MealCalendarResponse(
        month=month,
        registered_dates=[d.isoformat() for d in dates],
    )


@router.get("/{meal_id}", response_model=MealResponse)
async def get_single_meal(
    meal_id: uuid.UUID, user: CurrentUser, db: DB, request: Request
) -> MealResponse:
    """Get a single meal by ID."""
    meal = await get_meal(db, user.id, meal_id)
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )
    return meal_to_response(meal, base_url=str(request.base_url))


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(meal_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    """Delete a meal."""
    meal = await get_meal(db, user.id, meal_id)
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )
    await remove_meal(db, meal)
