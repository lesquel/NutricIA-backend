"""Use case: Update user food profile after a meal is logged."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Awaitable
from datetime import datetime, timezone
from typing import Any

from app.learning_loop.domain.entities import UserFoodProfile
from app.learning_loop.domain.ports import UserFoodProfileRepositoryPort


MealQueryFn = Callable[[uuid.UUID, int], Awaitable[list[Any]]]


def _empty_profile(user_id: uuid.UUID) -> UserFoodProfile:
    return UserFoodProfile(
        user_id=user_id,
        frequent_foods=[],
        avoided_tags=[],
        avg_daily_macros={"protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0},
        updated_at=datetime.now(timezone.utc),
    )


def _compute_avg_macros(meals: list[Any]) -> dict[str, float]:
    """Average macros from a list of Meal ORM objects (or any object with protein_g, carbs_g, fat_g)."""
    if not meals:
        return {"protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}

    total_protein = sum(getattr(m, "protein_g", 0.0) for m in meals)
    total_carbs = sum(getattr(m, "carbs_g", 0.0) for m in meals)
    total_fat = sum(getattr(m, "fat_g", 0.0) for m in meals)
    n = len(meals)

    return {
        "protein_g": round(total_protein / n, 2),
        "carbs_g": round(total_carbs / n, 2),
        "fat_g": round(total_fat / n, 2),
    }


class UpdateFoodProfileUseCase:
    """Increments food frequency and recomputes avg daily macros for a user."""

    def __init__(
        self,
        profile_repo: UserFoodProfileRepositoryPort,
        meal_query_fn: MealQueryFn,
    ) -> None:
        self._repo = profile_repo
        self._meal_query_fn = meal_query_fn

    async def execute(
        self,
        user_id: uuid.UUID,
        meal_canonical_name: str | None = None,
    ) -> UserFoodProfile:
        profile = await self._repo.get_by_user(user_id) or _empty_profile(user_id)

        if meal_canonical_name:
            profile = profile.add_food(meal_canonical_name)

        recent_meals = await self._meal_query_fn(user_id, 30)
        profile = UserFoodProfile(
            user_id=profile.user_id,
            frequent_foods=profile.frequent_foods,
            avoided_tags=profile.avoided_tags,
            avg_daily_macros=_compute_avg_macros(recent_meals),
            updated_at=datetime.now(timezone.utc),
        )

        return await self._repo.upsert(profile)
