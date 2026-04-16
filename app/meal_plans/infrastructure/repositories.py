"""Meal plans infrastructure — SQLAlchemy async repository implementation."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.meal_plans.domain.entities import Macros, MealPlan, PlannedMeal
from app.meal_plans.domain.errors import PlanNotFoundError
from app.meal_plans.infrastructure.models import MealPlanModel, PlannedMealModel


# ── UTC helpers ───────────────────────────────────────────────────────────────


def _ensure_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC tzinfo to naive datetimes returned by SQLite."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# ── Conversion helpers ────────────────────────────────────────────────────────


def _macros_from_dict(d: dict) -> Macros:
    return Macros(
        protein_g=float(d.get("protein_g", 0)),
        carbs_g=float(d.get("carbs_g", 0)),
        fat_g=float(d.get("fat_g", 0)),
    )


def _macros_to_dict(m: Macros) -> dict:
    return {
        "protein_g": m.protein_g,
        "carbs_g": m.carbs_g,
        "fat_g": m.fat_g,
    }


def _planned_meal_model_to_entity(model: PlannedMealModel) -> PlannedMeal:
    return PlannedMeal(
        id=model.id,
        plan_id=model.plan_id,
        day_of_week=model.day_of_week,
        meal_type=model.meal_type,  # type: ignore[arg-type]
        recipe_name=model.recipe_name,
        recipe_ingredients=list(model.recipe_ingredients),
        calories=model.calories,
        macros=_macros_from_dict(model.macros),
        cook_time_minutes=model.cook_time_minutes,
        difficulty=model.difficulty,  # type: ignore[arg-type]
        servings=model.servings,
        is_logged=model.is_logged,
        logged_meal_id=model.logged_meal_id,
    )


def _planned_meal_entity_to_model(entity: PlannedMeal) -> PlannedMealModel:
    return PlannedMealModel(
        id=entity.id,
        plan_id=entity.plan_id,
        day_of_week=entity.day_of_week,
        meal_type=entity.meal_type,
        recipe_name=entity.recipe_name,
        recipe_ingredients=entity.recipe_ingredients,
        calories=entity.calories,
        macros=_macros_to_dict(entity.macros),
        cook_time_minutes=entity.cook_time_minutes,
        difficulty=entity.difficulty,
        servings=entity.servings,
        is_logged=entity.is_logged,
        logged_meal_id=entity.logged_meal_id,
    )


def _week_start_to_date(raw: datetime) -> date:
    """Convert the stored DateTime back to a date.

    SQLAlchemy returns a ``datetime`` (Mapped[datetime]) for DateTime columns.
    SQLite may occasionally give a naive string at runtime, so we handle both.
    """
    if isinstance(raw, datetime):
        return raw.date()
    # Runtime guard for SQLite string edge case (mypy sees datetime only)
    return date.fromisoformat(str(raw))  # type: ignore[unreachable]


def _model_to_entity(model: MealPlanModel) -> MealPlan:
    week_start = _week_start_to_date(model.week_start)

    meals = [_planned_meal_model_to_entity(m) for m in model.meals]
    return MealPlan(
        id=model.id,
        user_id=model.user_id,
        week_start=week_start,
        target_calories=model.target_calories,
        target_macros=_macros_from_dict(model.target_macros),
        status=model.status,  # type: ignore[arg-type]
        approximation=model.approximation,
        meals=meals,
    )


def _entity_to_model(entity: MealPlan) -> MealPlanModel:
    return MealPlanModel(
        id=entity.id,
        user_id=entity.user_id,
        week_start=datetime(
            entity.week_start.year,
            entity.week_start.month,
            entity.week_start.day,
        ),
        target_calories=entity.target_calories,
        target_macros=_macros_to_dict(entity.target_macros),
        status=entity.status,
        approximation=entity.approximation,
    )


# ── Repository ────────────────────────────────────────────────────────────────


class MealPlanRepositoryImpl:
    """SQLAlchemy async implementation of MealPlanRepositoryPort."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, plan: MealPlan) -> MealPlan:
        """Persist a new meal plan with all its planned meals."""
        plan_model = _entity_to_model(plan)
        self._db.add(plan_model)
        await self._db.flush()

        for meal in plan.meals:
            meal_model = _planned_meal_entity_to_model(meal)
            self._db.add(meal_model)

        await self._db.flush()
        await self._db.refresh(plan_model)
        return _model_to_entity(plan_model)

    async def get(self, plan_id: uuid.UUID) -> MealPlan | None:
        """Get a meal plan by ID (includes all planned meals via selectin)."""
        result = await self._db.execute(
            select(MealPlanModel).where(MealPlanModel.id == plan_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_entity(model)

    async def get_current_for_user(
        self,
        user_id: uuid.UUID,
        week: date,
    ) -> MealPlan | None:
        """Return the active plan for the week that contains the given date."""
        result = await self._db.execute(
            select(MealPlanModel).where(
                MealPlanModel.user_id == user_id,
                MealPlanModel.week_start == datetime(week.year, week.month, week.day),
                MealPlanModel.status == "active",
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_entity(model)

    async def update(self, plan: MealPlan) -> MealPlan:
        """Persist changes to an existing plan (status, approximation, etc.)."""
        await self._db.execute(
            update(MealPlanModel)
            .where(MealPlanModel.id == plan.id)
            .values(
                status=plan.status,
                approximation=plan.approximation,
                target_calories=plan.target_calories,
                target_macros=_macros_to_dict(plan.target_macros),
            )
        )
        await self._db.flush()
        updated = await self.get(plan.id)
        if updated is None:
            raise PlanNotFoundError(f"MealPlan {plan.id} not found after update")
        return updated

    async def update_meal(
        self,
        plan_id: uuid.UUID,
        meal_id: uuid.UUID,
        planned_meal: PlannedMeal,
    ) -> PlannedMeal:
        """Replace a planned meal's recipe/macro data."""
        await self._db.execute(
            update(PlannedMealModel)
            .where(
                PlannedMealModel.id == meal_id,
                PlannedMealModel.plan_id == plan_id,
            )
            .values(
                meal_type=planned_meal.meal_type,
                recipe_name=planned_meal.recipe_name,
                recipe_ingredients=planned_meal.recipe_ingredients,
                calories=planned_meal.calories,
                macros=_macros_to_dict(planned_meal.macros),
                cook_time_minutes=planned_meal.cook_time_minutes,
                difficulty=planned_meal.difficulty,
                servings=planned_meal.servings,
            )
        )
        await self._db.flush()

        result = await self._db.execute(
            select(PlannedMealModel).where(PlannedMealModel.id == meal_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise PlanNotFoundError(f"PlannedMeal {meal_id} not found after update")
        return _planned_meal_model_to_entity(model)

    async def mark_meal_logged(
        self,
        plan_id: uuid.UUID,
        meal_id: uuid.UUID,
        logged_meal_id: uuid.UUID,
    ) -> PlannedMeal:
        """Mark a planned meal as logged and link to the created meal record."""
        await self._db.execute(
            update(PlannedMealModel)
            .where(
                PlannedMealModel.id == meal_id,
                PlannedMealModel.plan_id == plan_id,
            )
            .values(is_logged=True, logged_meal_id=logged_meal_id)
        )
        await self._db.flush()

        result = await self._db.execute(
            select(PlannedMealModel).where(PlannedMealModel.id == meal_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise PlanNotFoundError(
                f"PlannedMeal {meal_id} not found after mark_logged"
            )
        return _planned_meal_model_to_entity(model)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[MealPlan]:
        """List all plans for a user, newest first."""
        result = await self._db.execute(
            select(MealPlanModel)
            .where(MealPlanModel.user_id == user_id)
            .order_by(MealPlanModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        return [_model_to_entity(m) for m in models]
