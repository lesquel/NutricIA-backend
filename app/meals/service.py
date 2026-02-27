import io
import json
import logging
import uuid
from datetime import date, datetime, time, timezone

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.meals.ai_provider import get_analyzer
from app.meals.models import Meal, MealTag
from app.meals.schemas import MealCreate, MealResponse, ScanResult

logger = logging.getLogger(__name__)


async def analyze_meal_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
    """Compress image if needed and send to AI for analysis."""
    processed = _compress_image(image_bytes)
    analyzer = get_analyzer()
    return await analyzer.analyze(processed, mime_type)


def _compress_image(image_bytes: bytes) -> bytes:
    """Resize and compress image to stay under size limits."""
    if len(image_bytes) <= settings.max_image_bytes:
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes))

    # Resize keeping aspect ratio
    max_px = settings.max_image_size_px
    img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)

    # Save with reduced quality
    buffer = io.BytesIO()
    img_format = "JPEG" if img.mode == "RGB" else "PNG"
    if img.mode == "RGBA":
        img = img.convert("RGB")
        img_format = "JPEG"

    img.save(buffer, format=img_format, quality=80, optimize=True)
    return buffer.getvalue()


async def create_meal(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: MealCreate,
) -> Meal:
    """Save a confirmed meal to the database."""
    meal = Meal(
        user_id=user_id,
        name=data.name,
        image_url=data.image_url,
        calories=data.calories,
        protein_g=data.protein_g,
        carbs_g=data.carbs_g,
        fat_g=data.fat_g,
        meal_type=data.meal_type,
        confidence_score=data.confidence_score,
        logged_at=data.logged_at or datetime.now(timezone.utc),
    )
    db.add(meal)
    await db.flush()

    # Add tags
    for tag_label in data.tags:
        tag = MealTag(meal_id=meal.id, label=tag_label)
        db.add(tag)

    await db.flush()
    await db.refresh(meal)
    return meal


async def get_daily_meals(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date,
) -> list[Meal]:
    """Get all meals for a user on a specific date."""
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

    result = await db.execute(
        select(Meal)
        .where(
            Meal.user_id == user_id,
            Meal.logged_at >= start,
            Meal.logged_at <= end,
        )
        .order_by(Meal.logged_at)
    )
    return list(result.scalars().all())


async def get_meal_by_id(
    db: AsyncSession,
    user_id: uuid.UUID,
    meal_id: uuid.UUID,
) -> Meal | None:
    """Get a single meal by ID, scoped to user."""
    result = await db.execute(
        select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_meal(
    db: AsyncSession,
    meal: Meal,
) -> None:
    """Delete a meal."""
    await db.delete(meal)


def meal_to_response(meal: Meal) -> MealResponse:
    """Convert Meal model to response schema."""
    return MealResponse(
        id=str(meal.id),
        name=meal.name,
        image_url=meal.image_url,
        calories=meal.calories,
        protein_g=meal.protein_g,
        carbs_g=meal.carbs_g,
        fat_g=meal.fat_g,
        meal_type=meal.meal_type,
        confidence_score=meal.confidence_score,
        tags=[tag.label for tag in meal.tags],
        logged_at=meal.logged_at,
        created_at=meal.created_at,
    )
