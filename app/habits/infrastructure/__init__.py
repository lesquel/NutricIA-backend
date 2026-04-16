"""Habits infrastructure — SQLAlchemy models."""

import uuid
from datetime import date as DateType, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.infrastructure import Base


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    icon: Mapped[str] = mapped_column(String(50), default="eco")
    plant_type: Mapped[str] = mapped_column(
        String(50), default="fern"
    )  # fern | palm | mint | cactus
    level: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    check_ins: Mapped[list["HabitCheckIn"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan", lazy="selectin"
    )


class HabitCheckIn(Base):
    __tablename__ = "habit_check_ins"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    habit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("habits.id", ondelete="CASCADE"), index=True
    )
    checked_at: Mapped[DateType] = mapped_column(Date)

    habit: Mapped["Habit"] = relationship(back_populates="check_ins")


class WaterIntake(Base):
    __tablename__ = "water_intake"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    cups: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[DateType] = mapped_column(Date)
