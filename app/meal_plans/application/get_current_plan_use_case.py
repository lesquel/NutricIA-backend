"""Use case: Get the current active meal plan for a user."""

from __future__ import annotations

import uuid
from datetime import date

from app.meal_plans.domain.entities import MealPlan
from app.meal_plans.domain.ports import MealPlanRepositoryPort


class GetCurrentPlanUseCase:
    """Return the active plan for the week containing the given date (or today)."""

    def __init__(self, plan_repo: MealPlanRepositoryPort) -> None:
        self._repo = plan_repo

    async def execute(
        self,
        user_id: uuid.UUID,
        week: date | None = None,
    ) -> MealPlan | None:
        if week is None:
            week = date.today()
        return await self._repo.get_current_for_user(user_id, week=week)
