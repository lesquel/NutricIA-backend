"""Use case: Generate a new weekly meal plan."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from app.meal_plans.domain.entities import DietaryConstraints, Macros, MealPlan
from app.meal_plans.domain.ports import MealPlanRepositoryPort, PlanGeneratorPort


class GeneratePlanUseCase:
    """Generate a weekly meal plan and persist it.

    If a plan already exists for the given week_start, it is archived before
    the new one is generated (no duplicate active plans per user per week).
    """

    def __init__(
        self,
        plan_repo: MealPlanRepositoryPort,
        generator: PlanGeneratorPort,
    ) -> None:
        self._repo = plan_repo
        self._generator = generator

    async def execute(
        self,
        user_id: uuid.UUID,
        target_calories: int,
        target_macros: Macros,
        constraints: DietaryConstraints,
        context: dict[str, Any],
        week_start: date,
    ) -> MealPlan:
        # Archive existing active plan for this week if any
        existing = await self._repo.get_current_for_user(user_id, week=week_start)
        if existing is not None:
            archived = MealPlan(
                id=existing.id,
                user_id=existing.user_id,
                week_start=existing.week_start,
                target_calories=existing.target_calories,
                target_macros=existing.target_macros,
                status="archived",
                approximation=existing.approximation,
                meals=existing.meals,
            )
            await self._repo.update(archived)

        # Generate new plan
        plan = await self._generator.generate(  # type: ignore[call-arg]
            user_id=user_id,
            target_calories=target_calories,
            target_macros=target_macros,
            constraints=constraints,
            context=context,
            week_start=week_start,
        )

        # Persist and return
        return await self._repo.create(plan)
