"""Meal plans presentation — FastAPI router."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import DB, CurrentUser
from app.meal_plans.application.generate_plan_use_case import GeneratePlanUseCase
from app.meal_plans.application.get_current_plan_use_case import GetCurrentPlanUseCase
from app.meal_plans.application.log_meal_use_case import LogMealUseCase
from app.meal_plans.application.swap_meal_use_case import SwapMealUseCase
from app.meal_plans.domain.entities import (
    DietaryConstraints,
    Macros,
    MealPlan,
    PlannedMeal,
)
from app.meal_plans.domain.errors import MacroTargetUnreachableError, PlanNotFoundError
from app.meal_plans.infrastructure.plan_generator import LLMPlanGenerator
from app.meal_plans.infrastructure.repositories import MealPlanRepositoryImpl
from app.meal_plans.presentation import (
    GeneratePlanRequest,
    LogMealResponse,
    MealPlanResponse,
    MacrosSchema,
    PlannedMealResponse,
    SwapMealRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["meal-plans"])

# ── Simple in-memory rate limiter for /generate (1 req/60s per user) ─────────

_generate_last_call: dict[str, float] = defaultdict(float)
_RATE_LIMIT_SECONDS = 60


def _check_generate_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    last = _generate_last_call[user_id]
    if now - last < _RATE_LIMIT_SECONDS:
        remaining = int(_RATE_LIMIT_SECONDS - (now - last))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Plan generation is rate-limited: retry in {remaining}s",
        )
    _generate_last_call[user_id] = now


# ── Dependency factories ──────────────────────────────────────────────────────


def get_plan_repo(db: DB) -> MealPlanRepositoryImpl:
    return MealPlanRepositoryImpl(db)


_plan_generator_singleton: LLMPlanGenerator | None = None


def get_plan_generator() -> LLMPlanGenerator:
    global _plan_generator_singleton
    if _plan_generator_singleton is None:
        _plan_generator_singleton = LLMPlanGenerator()
    return _plan_generator_singleton


PlanRepo = Annotated[MealPlanRepositoryImpl, Depends(get_plan_repo)]
PlanGenerator = Annotated[LLMPlanGenerator, Depends(get_plan_generator)]


# ── Mapping helpers ───────────────────────────────────────────────────────────


def _macros_response(m: Macros) -> MacrosSchema:
    return MacrosSchema(protein_g=m.protein_g, carbs_g=m.carbs_g, fat_g=m.fat_g)


def _planned_meal_response(pm: PlannedMeal) -> PlannedMealResponse:
    return PlannedMealResponse(
        id=pm.id,
        plan_id=pm.plan_id,
        day_of_week=pm.day_of_week,
        meal_type=pm.meal_type,
        recipe_name=pm.recipe_name,
        recipe_ingredients=pm.recipe_ingredients,
        calories=pm.calories,
        macros=_macros_response(pm.macros),
        cook_time_minutes=pm.cook_time_minutes,
        difficulty=pm.difficulty,
        servings=pm.servings,
        is_logged=pm.is_logged,
        logged_meal_id=pm.logged_meal_id,
    )


def _plan_response(plan: MealPlan) -> MealPlanResponse:
    return MealPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        week_start=plan.week_start,
        target_calories=plan.target_calories,
        target_macros=_macros_response(plan.target_macros),
        status=plan.status,
        approximation=plan.approximation,
        meals=[_planned_meal_response(m) for m in plan.meals],
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/generate",
    response_model=MealPlanResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_plan(
    body: GeneratePlanRequest,
    user: CurrentUser,
    repo: PlanRepo,
    generator: PlanGenerator,
) -> MealPlanResponse:
    """Generate a new 7-day meal plan for the current user.

    Rate-limited to 1 request per minute per user (LLM generation is expensive).
    """
    _check_generate_rate_limit(str(user.id))

    week_start = body.week_start
    if week_start is None:
        today = date.today()
        # Monday of the current week
        week_start = today  # use today if not specified; generator uses it as-is

    target_macros = Macros(
        protein_g=body.target_macros.protein_g,
        carbs_g=body.target_macros.carbs_g,
        fat_g=body.target_macros.fat_g,
    )
    constraints = DietaryConstraints(
        vegetarian=body.constraints.vegetarian,
        vegan=body.constraints.vegan,
        gluten_free=body.constraints.gluten_free,
        allergies=body.constraints.allergies,
    )

    use_case = GeneratePlanUseCase(plan_repo=repo, generator=generator)
    try:
        plan = await use_case.execute(
            user_id=user.id,
            target_calories=body.target_calories,
            target_macros=target_macros,
            constraints=constraints,
            context=body.context,
            week_start=week_start,
        )
    except MacroTargetUnreachableError as exc:
        # Return plan with approximation=True (already set by generator)
        logger.warning("Macro target unreachable for user %s: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Unexpected error generating plan for user %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Plan generation failed. Please try again.",
        )

    return _plan_response(plan)


@router.get("/current", response_model=MealPlanResponse | None)
async def get_current_plan(
    user: CurrentUser,
    repo: PlanRepo,
    week: date | None = None,
) -> MealPlanResponse | None:
    """Return the active meal plan for the current week (or specified week)."""
    use_case = GetCurrentPlanUseCase(plan_repo=repo)
    plan = await use_case.execute(user_id=user.id, week=week)
    if plan is None:
        return None
    return _plan_response(plan)


@router.get("/{plan_id}", response_model=MealPlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    user: CurrentUser,
    repo: PlanRepo,
) -> MealPlanResponse:
    """Get a specific meal plan by ID."""
    plan = await repo.get(plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    return _plan_response(plan)


@router.patch(
    "/{plan_id}/meals/{meal_id}",
    response_model=PlannedMealResponse,
)
async def swap_meal(
    plan_id: uuid.UUID,
    meal_id: uuid.UUID,
    body: SwapMealRequest,
    user: CurrentUser,
    repo: PlanRepo,
    generator: PlanGenerator,
) -> PlannedMealResponse:
    """Swap a planned meal with a freshly generated alternative."""
    constraints = None
    if body.constraints is not None:
        constraints = DietaryConstraints(
            vegetarian=body.constraints.vegetarian,
            vegan=body.constraints.vegan,
            gluten_free=body.constraints.gluten_free,
            allergies=body.constraints.allergies,
        )

    use_case = SwapMealUseCase(plan_repo=repo, generator=generator)
    try:
        updated_meal = await use_case.execute(
            user_id=user.id,
            plan_id=plan_id,
            meal_id=meal_id,
            swap_constraints=constraints,
            context=body.context,
        )
    except PlanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan or meal not found",
        )
    except Exception:
        logger.exception("Error swapping meal %s in plan %s", meal_id, plan_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Meal swap failed. Please try again.",
        )

    return _planned_meal_response(updated_meal)


@router.post(
    "/{plan_id}/meals/{meal_id}/log",
    response_model=LogMealResponse,
    status_code=status.HTTP_200_OK,
)
async def log_meal(
    plan_id: uuid.UUID,
    meal_id: uuid.UUID,
    user: CurrentUser,
    repo: PlanRepo,
    db: DB,
) -> LogMealResponse:
    """Log a planned meal — creates a Meal entry and marks it as logged."""
    use_case = LogMealUseCase(plan_repo=repo, db=db)
    try:
        result = await use_case.execute(
            user_id=user.id,
            plan_id=plan_id,
            meal_id=meal_id,
        )
    except PlanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan or meal not found",
        )
    except Exception:
        logger.exception("Error logging meal %s in plan %s", meal_id, plan_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Meal logging failed. Please try again.",
        )

    return LogMealResponse(**result)
