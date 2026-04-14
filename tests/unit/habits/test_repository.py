"""Tests for habits repository layer."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import User
from app.habits.application.habit_use_cases import create_habit
from app.habits.presentation import HabitCreate


@pytest.mark.asyncio
async def test_get_habit_by_id_and_user_returns_habit(
    db_session: AsyncSession, test_user: User
):
    """Repository returns a Habit when id and user_id match."""
    from app.habits.infrastructure.repository import get_habit_by_id_and_user

    data = HabitCreate(name="Repo Test", icon="eco", plant_type="fern")
    habit = await create_habit(db_session, test_user.id, data)

    result = await get_habit_by_id_and_user(db_session, habit.id, test_user.id)

    assert result is not None
    assert result.id == habit.id
    assert result.name == "Repo Test"


@pytest.mark.asyncio
async def test_get_habit_by_id_and_user_returns_none_for_wrong_user(
    db_session: AsyncSession, test_user: User
):
    """Repository returns None when user_id doesn't match."""
    from app.habits.infrastructure.repository import get_habit_by_id_and_user

    data = HabitCreate(name="Not Yours", icon="eco", plant_type="fern")
    habit = await create_habit(db_session, test_user.id, data)

    other_user_id = uuid.uuid4()
    result = await get_habit_by_id_and_user(db_session, habit.id, other_user_id)

    assert result is None


@pytest.mark.asyncio
async def test_get_habit_by_id_and_user_returns_none_for_missing_id(
    db_session: AsyncSession, test_user: User
):
    """Repository returns None when habit_id doesn't exist."""
    from app.habits.infrastructure.repository import get_habit_by_id_and_user

    result = await get_habit_by_id_and_user(db_session, uuid.uuid4(), test_user.id)

    assert result is None


@pytest.mark.asyncio
async def test_delete_habit_removes_it(db_session: AsyncSession, test_user: User):
    """Repository deletes the habit from the database."""
    from app.habits.infrastructure.repository import (
        delete_habit,
        get_habit_by_id_and_user,
    )

    data = HabitCreate(name="To Delete", icon="eco", plant_type="fern")
    habit = await create_habit(db_session, test_user.id, data)
    habit_id = habit.id

    await delete_habit(db_session, habit)
    await db_session.flush()

    result = await get_habit_by_id_and_user(db_session, habit_id, test_user.id)
    assert result is None
