"""Meal plans infrastructure — SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.infrastructure import Base


class MealPlanModel(Base):
    """ORM mapping for the meal_plans table (migration 009)."""

    __tablename__ = "meal_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start: Mapped[datetime] = mapped_column(nullable=False)
    target_calories: Mapped[int] = mapped_column(Integer, nullable=False)
    target_macros: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    approximation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    meals: Mapped[list["PlannedMealModel"]] = relationship(
        "PlannedMealModel",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlannedMealModel(Base):
    """ORM mapping for the planned_meals table (migration 009)."""

    __tablename__ = "planned_meals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("meal_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    recipe_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipe_ingredients: Mapped[list] = mapped_column(JSON, nullable=False)
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    macros: Mapped[dict] = mapped_column(JSON, nullable=False)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    servings: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_logged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    logged_meal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("meals.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship back to plan
    plan: Mapped["MealPlanModel"] = relationship(
        "MealPlanModel", back_populates="meals"
    )
