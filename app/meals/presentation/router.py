"""Meals presentation — FastAPI router."""

import json
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status

from app.dependencies import DB, CurrentUser
from app.meals.application.embedding_hook import generate_meal_embedding
from app.meals.domain import FoodAnalysisError, AIProviderError
from app.meals.application.scan_food import scan_food
from app.meals.application.meal_crud import (
    save_meal,
    list_meals,
    get_meal,
    remove_meal,
    meal_to_response,
    get_meal_dates_in_month,
    list_meals_last_n_days,
    update_meal,
)
from app.meals.presentation import (
    ScanResult,
    MealCreate,
    MealResponse,
    MealListResponse,
    MealImageUploadResponse,
    MealCalendarResponse,
    MealUpdate,
)
from app.config import settings


def _get_embeddings_provider() -> Any:
    """Return the configured embeddings provider, or None if not configured."""
    from app.shared.infrastructure.embeddings import (
        DualEmbeddingsProvider,
        GeminiEmbeddingsProvider,
        OpenAIEmbeddingsProvider,
    )

    if settings.google_api_key and settings.openai_api_key:
        return DualEmbeddingsProvider(
            primary=GeminiEmbeddingsProvider(settings.google_api_key),
            fallback=OpenAIEmbeddingsProvider(settings.openai_api_key),
        )
    if settings.google_api_key:
        return GeminiEmbeddingsProvider(settings.google_api_key)
    if settings.openai_api_key:
        return OpenAIEmbeddingsProvider(settings.openai_api_key)
    return None


def _get_meal_vector_store() -> Any:
    """Return the meal embeddings vector store adapter (env-driven)."""
    from app.shared.infrastructure.vector_store import get_vector_store

    return get_vector_store("meal_embeddings")


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meals", tags=["meals"])


@router.post("/scan", response_model=ScanResult)
async def scan_meal(file: UploadFile, user: CurrentUser, db: DB) -> ScanResult:
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

    # Enrich prompt with user food profile if available
    profile_hint: dict[str, Any] | None = None
    try:
        from app.learning_loop.infrastructure.repositories import (
            UserFoodProfileRepositoryImpl,
        )

        profile_repo = UserFoodProfileRepositoryImpl(db)
        profile = await profile_repo.get_by_user(user.id)
        if profile is not None:
            profile_hint = {
                "frequent_foods": profile.frequent_foods,
                "avg_daily_macros": profile.avg_daily_macros,
            }
    except Exception:
        logger.debug("Could not load food profile for scan enrichment", exc_info=True)

    try:
        return await scan_food(image_bytes, file.content_type, profile_hint)
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
async def upload_meal_image(
    file: UploadFile, user: CurrentUser
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

    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    relative_dir = Path("uploads") / "meals" / str(user.id)
    absolute_dir = Path.cwd() / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{suffix}"
    file_path = absolute_dir / filename
    file_path.write_bytes(image_bytes)

    image_url = f"{settings.base_url}/{relative_dir.as_posix()}/{filename}"
    return MealImageUploadResponse(image_url=image_url)


@router.post("", response_model=MealResponse, status_code=status.HTTP_201_CREATED)
async def add_meal(
    body: MealCreate,
    user: CurrentUser,
    db: DB,
    background_tasks: BackgroundTasks,
) -> MealResponse:
    """Confirm and save a scanned or manually entered meal.

    After saving, schedules a background task to generate and upsert the
    meal embedding.  The response is returned immediately without waiting
    for the embedding to complete.
    """
    meal = await save_meal(db, user.id, body)

    # Fire-and-forget: generate embedding in background
    embeddings_provider = _get_embeddings_provider()
    if embeddings_provider is not None:
        vector_store = _get_meal_vector_store()
        background_tasks.add_task(
            generate_meal_embedding,
            meal,
            vector_store,
            embeddings_provider,
        )

    # Fire-and-forget: update user food profile (learning loop iter 4A)
    background_tasks.add_task(
        _update_food_profile_background,
        user.id,
        meal.name,
    )

    return meal_to_response(meal)


async def _update_food_profile_background(
    user_id: uuid.UUID,
    meal_name: str,
) -> None:
    """Background task: update user food profile after meal save."""
    try:
        from app.learning_loop.application.update_food_profile_use_case import (
            UpdateFoodProfileUseCase,
        )
        from app.learning_loop.infrastructure.repositories import (
            UserFoodProfileRepositoryImpl,
        )
        from app.shared.infrastructure import async_session

        async with async_session() as session:
            profile_repo = UserFoodProfileRepositoryImpl(session)
            use_case = UpdateFoodProfileUseCase(
                profile_repo=profile_repo,
                meal_query_fn=lambda uid, days: list_meals_last_n_days(
                    session, uid, days
                ),
            )
            await use_case.execute(user_id, meal_name)
            await session.commit()
    except Exception:
        logger.debug("Failed to update food profile in background", exc_info=True)


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
        registered_dates=[d if isinstance(d, str) else d.isoformat() for d in dates],
    )


@router.get("/{meal_id}", response_model=MealResponse)
async def get_single_meal(
    meal_id: uuid.UUID, user: CurrentUser, db: DB
) -> MealResponse:
    """Get a single meal by ID."""
    meal = await get_meal(db, user.id, meal_id)
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )
    return meal_to_response(meal)


@router.patch("/{meal_id}", response_model=MealResponse)
async def patch_meal(
    meal_id: uuid.UUID,
    body: MealUpdate,
    user: CurrentUser,
    db: DB,
    background_tasks: BackgroundTasks,
) -> MealResponse:
    """Partially update a meal. Tracks corrections for low-confidence AI scans."""
    meal = await get_meal(db, user.id, meal_id)
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )

    original_confidence = meal.confidence_score or 0.0
    original_scan_raw = meal.ai_raw_response

    # Track scan correction inline (low-confidence only) — uses same db session
    if original_confidence < 0.6 and original_scan_raw:
        try:
            original_scan = json.loads(original_scan_raw)
        except (json.JSONDecodeError, TypeError):
            original_scan = {}

        corrected_values: dict[str, Any] = {}
        for field in ("name", "calories", "protein_g", "carbs_g", "fat_g"):
            new_val = getattr(body, field, None)
            if new_val is not None:
                corrected_values[field] = new_val

        if corrected_values:
            try:
                from app.learning_loop.application.track_scan_correction_use_case import (
                    TrackScanCorrectionUseCase,
                )
                from app.learning_loop.infrastructure.repositories import (
                    ScanCorrectionRepositoryImpl,
                )

                correction_repo = ScanCorrectionRepositoryImpl(db)
                use_case = TrackScanCorrectionUseCase(correction_repo)
                await use_case.execute(
                    user_id=user.id,
                    meal_id=meal_id,
                    original_scan=original_scan,
                    corrected_values=corrected_values,
                    original_confidence=original_confidence,
                )
            except Exception:
                logger.debug("Failed to track scan correction", exc_info=True)

    updated = await update_meal(db, meal, body)
    return meal_to_response(updated)


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(meal_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    """Delete a meal."""
    meal = await get_meal(db, user.id, meal_id)
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )
    await remove_meal(db, meal)
