"""Use case: Habit CRUD and check-in logic."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.habits.infrastructure.models import Habit, HabitCheckIn, WaterIntake
from app.habits.presentation import HabitCreate, HabitResponse


async def create_habit(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: HabitCreate,
) -> Habit:
    """Create a new habit (plant a seed)."""
    habit = Habit(
        user_id=user_id,
        name=data.name,
        icon=data.icon,
        plant_type=data.plant_type,
    )
    db.add(habit)
    await db.flush()
    await db.refresh(habit)
    return habit


async def get_user_habits(db: AsyncSession, user_id: uuid.UUID) -> list[Habit]:
    """List all habits for a user."""
    result = await db.execute(
        select(Habit).where(Habit.user_id == user_id).order_by(Habit.created_at)
    )
    return list(result.scalars().all())


async def check_in_habit(
    db: AsyncSession,
    habit: Habit,
    target_date: date | None = None,
) -> tuple[int, int]:
    """Check in on a habit for today. Returns (new_streak, new_level)."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    # Check if already checked in today
    existing = await db.execute(
        select(HabitCheckIn).where(
            HabitCheckIn.habit_id == habit.id,
            HabitCheckIn.checked_at == target_date,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return habit.streak_days, habit.level

    # Check if yesterday was checked in (for streak)
    yesterday = target_date - timedelta(days=1)
    yesterday_check = await db.execute(
        select(HabitCheckIn).where(
            HabitCheckIn.habit_id == habit.id,
            HabitCheckIn.checked_at == yesterday,
        )
    )

    if yesterday_check.scalar_one_or_none() is not None:
        habit.streak_days += 1
    else:
        habit.streak_days = 1  # Reset streak, start fresh

    # Level up: every 7 days of streak
    habit.level = habit.streak_days // 7

    # Save check-in
    check_in = HabitCheckIn(habit_id=habit.id, checked_at=target_date)
    db.add(check_in)
    await db.flush()

    return habit.streak_days, habit.level


def compute_plant_state(streak_days: int) -> Literal["healthy", "growing", "wilted"]:
    """Determine plant health based on streak."""
    if streak_days == 0:
        return "wilted"
    if streak_days <= 3:
        return "growing"
    return "healthy"


def compute_progress_percentage(streak_days: int) -> float:
    """Progress within current level (0–100). Level = streak // 7."""
    return round((streak_days % 7) / 7 * 100, 1)


async def is_checked_today(db: AsyncSession, habit_id: uuid.UUID) -> bool:
    """Check if a habit has been checked in today."""
    result = await db.execute(
        select(HabitCheckIn).where(
            HabitCheckIn.habit_id == habit_id,
            HabitCheckIn.checked_at == datetime.now(timezone.utc).date(),
        )
    )
    return result.scalar_one_or_none() is not None


async def habit_to_response(db: AsyncSession, habit: Habit) -> HabitResponse:
    """Convert Habit model to response schema."""
    checked = await is_checked_today(db, habit.id)
    return HabitResponse(
        id=str(habit.id),
        name=habit.name,
        icon=habit.icon,
        plant_type=habit.plant_type,
        level=habit.level,
        streak_days=habit.streak_days,
        plant_state=compute_plant_state(habit.streak_days),
        progress_percentage=compute_progress_percentage(habit.streak_days),
        checked_today=checked,
    )


# ── Water Tracking ──────────────────────────


async def log_water(
    db: AsyncSession,
    user_id: uuid.UUID,
    cups: int,
    target_date: date | None = None,
) -> WaterIntake:
    """Set water cups for today (upsert)."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    result = await db.execute(
        select(WaterIntake).where(
            WaterIntake.user_id == user_id,
            WaterIntake.date == target_date,
        )
    )
    entry = result.scalar_one_or_none()

    if entry is not None:
        entry.cups = cups
    else:
        entry = WaterIntake(user_id=user_id, cups=cups, date=target_date)
        db.add(entry)

    await db.flush()
    return entry


async def get_water_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date | None = None,
) -> WaterIntake | None:
    """Get water intake for a date."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    result = await db.execute(
        select(WaterIntake).where(
            WaterIntake.user_id == user_id,
            WaterIntake.date == target_date,
        )
    )
    return result.scalar_one_or_none()
