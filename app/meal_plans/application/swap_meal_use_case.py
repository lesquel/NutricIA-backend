"""Use case: Swap a single planned meal with a freshly generated alternative."""

from __future__ import annotations

import uuid
from typing import Any

from app.meal_plans.domain.entities import DietaryConstraints, PlannedMeal
from app.meal_plans.domain.errors import PlanNotFoundError
from app.meal_plans.domain.ports import MealPlanRepositoryPort
from app.meal_plans.infrastructure.plan_generator import LLMPlanGenerator


class SwapMealUseCase:
    """Generate a replacement for one planned meal and persist it."""

    def __init__(
        self,
        plan_repo: MealPlanRepositoryPort,
        generator: LLMPlanGenerator,
    ) -> None:
        self._repo = plan_repo
        self._generator = generator

    async def execute(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        meal_id: uuid.UUID,
        swap_constraints: DietaryConstraints | None = None,
        context: dict[str, Any] | None = None,
    ) -> PlannedMeal:
        # Verify plan ownership
        plan = await self._repo.get(plan_id)
        if plan is None or plan.user_id != user_id:
            raise PlanNotFoundError(f"Plan {plan_id} not found for user {user_id}")

        # Find the existing meal to know its day/type
        existing_meal = next((m for m in plan.meals if m.id == meal_id), None)
        if existing_meal is None:
            raise PlanNotFoundError(
                f"PlannedMeal {meal_id} not found in plan {plan_id}"
            )

        constraints = swap_constraints or DietaryConstraints(
            vegetarian=False, vegan=False, gluten_free=False, allergies=[]
        )
        ctx = context or {}

        # Generate replacement (simpler single-meal call)
        new_meal = await self._generator.generate_single_meal(
            user_id=user_id,
            plan_id=plan_id,
            day_of_week=existing_meal.day_of_week,
            meal_type=existing_meal.meal_type,
            target_calories=plan.target_calories,
            target_macros=plan.target_macros,
            constraints=constraints,
            context=ctx,
        )

        # Use the same ID so the client reference doesn't break
        new_meal_with_same_id = PlannedMeal(
            id=meal_id,
            plan_id=new_meal.plan_id,
            day_of_week=new_meal.day_of_week,
            meal_type=new_meal.meal_type,
            recipe_name=new_meal.recipe_name,
            recipe_ingredients=new_meal.recipe_ingredients,
            calories=new_meal.calories,
            macros=new_meal.macros,
            cook_time_minutes=new_meal.cook_time_minutes,
            difficulty=new_meal.difficulty,
            servings=new_meal.servings,
            is_logged=False,
            logged_meal_id=None,
        )

        return await self._repo.update_meal(plan_id, meal_id, new_meal_with_same_id)
