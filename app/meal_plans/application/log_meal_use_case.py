"""Use case: Log a planned meal (create a Meal record and mark as logged)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.meal_plans.domain.errors import PlanNotFoundError
from app.meal_plans.domain.ports import MealPlanRepositoryPort
from app.meals.infrastructure import Meal


class LogMealUseCase:
    """Mark a planned meal as logged and create a corresponding Meal record."""

    def __init__(
        self,
        plan_repo: MealPlanRepositoryPort,
        db: AsyncSession,
    ) -> None:
        self._repo = plan_repo
        self._db = db

    async def execute(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        meal_id: uuid.UUID,
    ) -> dict[str, Any]:
        # Verify plan ownership
        plan = await self._repo.get(plan_id)
        if plan is None or plan.user_id != user_id:
            raise PlanNotFoundError(f"Plan {plan_id} not found for user {user_id}")

        # Find the planned meal
        planned = next((m for m in plan.meals if m.id == meal_id), None)
        if planned is None:
            raise PlanNotFoundError(
                f"PlannedMeal {meal_id} not found in plan {plan_id}"
            )

        if planned.is_logged:
            # Already logged — return existing info
            return {
                "meal_id": str(planned.logged_meal_id),
                "planned_meal_id": str(planned.id),
                "already_logged": True,
            }

        # Create a regular Meal record from planned meal data
        new_meal = Meal(
            id=uuid.uuid4(),
            user_id=user_id,
            name=planned.recipe_name,
            calories=planned.calories,
            protein_g=planned.macros.protein_g,
            carbs_g=planned.macros.carbs_g,
            fat_g=planned.macros.fat_g,
            meal_type=planned.meal_type,
            confidence_score=1.0,  # planned meals are high-confidence
            ai_raw_response=None,
            image_url=None,
        )
        self._db.add(new_meal)
        await self._db.flush()
        await self._db.refresh(new_meal)

        # Mark planned meal as logged and link to the new meal
        await self._repo.mark_meal_logged(plan_id, meal_id, new_meal.id)

        return {
            "meal_id": str(new_meal.id),
            "planned_meal_id": str(planned.id),
            "already_logged": False,
        }
