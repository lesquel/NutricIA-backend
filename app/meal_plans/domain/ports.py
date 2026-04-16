"""Meal plans domain ports (Protocol interfaces)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol, runtime_checkable

from app.meal_plans.domain.entities import (
    DietaryConstraints,
    Macros,
    MealPlan,
    PlannedMeal,
)


@runtime_checkable
class MealPlanRepositoryPort(Protocol):
    async def create(self, plan: MealPlan) -> MealPlan: ...

    async def get(self, id: uuid.UUID) -> MealPlan | None: ...

    async def get_current_for_user(
        self,
        user_id: uuid.UUID,
        week: date,
    ) -> MealPlan | None: ...

    async def update(self, plan: MealPlan) -> MealPlan: ...

    async def update_meal(
        self,
        plan_id: uuid.UUID,
        meal_id: uuid.UUID,
        planned_meal: PlannedMeal,
    ) -> PlannedMeal: ...

    async def mark_meal_logged(
        self,
        plan_id: uuid.UUID,
        meal_id: uuid.UUID,
        logged_meal_id: uuid.UUID,
    ) -> PlannedMeal: ...


@runtime_checkable
class PlanGeneratorPort(Protocol):
    async def generate(
        self,
        user_id: uuid.UUID,
        target_calories: int,
        target_macros: Macros,
        constraints: DietaryConstraints,
        context: dict[str, Any],
    ) -> MealPlan: ...
