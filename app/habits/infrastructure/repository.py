"""Habits infrastructure — repository layer."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.habits.infrastructure.models import Habit


async def get_habit_by_id_and_user(
    db: AsyncSession, habit_id: uuid.UUID, user_id: uuid.UUID
) -> Habit | None:
    """Fetch a habit by its ID, scoped to a specific user."""
    result = await db.execute(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_habit(db: AsyncSession, habit: Habit) -> None:
    """Remove a habit from the database."""
    await db.delete(habit)
