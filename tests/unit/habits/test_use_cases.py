"""Tests for habit use cases."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import User
from app.habits.application.habit_use_cases import (
    check_in_habit,
    create_habit,
    get_water_log,
    log_water,
)
from app.habits.presentation import HabitCreate


@pytest.mark.asyncio
async def test_create_habit_creates_new_habit(
    db_session: AsyncSession, test_user: User
):
    """Test creating a new habit creates it in the database."""
    data = HabitCreate(
        name="Drink water",
        icon="water_drop",
        plant_type="mint",
    )

    habit = await create_habit(db_session, test_user.id, data)

    assert habit.id is not None
    assert habit.name == "Drink water"
    assert habit.icon == "water_drop"
    assert habit.plant_type == "mint"
    assert habit.user_id == test_user.id
    assert habit.streak_days == 0
    assert habit.level == 0


@pytest.mark.asyncio
async def test_create_habit_with_plant_type(db_session: AsyncSession, test_user: User):
    """Test creating a habit with different plant types."""
    data = HabitCreate(
        name="Morning stretch",
        icon="self_improvement",
        plant_type="palm",
    )

    habit = await create_habit(db_session, test_user.id, data)

    assert habit.plant_type == "palm"
    assert habit.name == "Morning stretch"


@pytest.mark.asyncio
async def test_check_in_habit_increments_streak(
    db_session: AsyncSession, test_user: User
):
    """Test checking in a habit increments the streak."""
    habit_data = HabitCreate(name="Yoga", icon="self_improvement", plant_type="fern")
    habit = await create_habit(db_session, test_user.id, habit_data)

    new_streak, new_level = await check_in_habit(db_session, habit)

    assert new_streak == 1
    assert new_level == 0


@pytest.mark.asyncio
async def test_check_in_multiple_days_tracks_streak(
    db_session: AsyncSession, test_user: User
):
    """Test checking in on consecutive days tracks the streak correctly."""
    habit_data = HabitCreate(name="Meditation", icon="spa", plant_type="fern")
    habit = await create_habit(db_session, test_user.id, habit_data)

    today = date.today()
    yesterday = today - timedelta(days=1)

    await check_in_habit(db_session, habit, yesterday)

    new_streak, new_level = await check_in_habit(db_session, habit, today)

    assert new_streak == 2
    assert new_level == 0


@pytest.mark.asyncio
async def test_check_in_non_consecutive_days_resets_streak(
    db_session: AsyncSession, test_user: User
):
    """Test checking in after missing days resets streak to 1."""
    habit_data = HabitCreate(name="Reading", icon="menu_book", plant_type="fern")
    habit = await create_habit(db_session, test_user.id, habit_data)

    today = date.today()
    two_days_ago = today - timedelta(days=2)

    await check_in_habit(db_session, habit, two_days_ago)

    new_streak, _ = await check_in_habit(db_session, habit, today)

    assert new_streak == 1


@pytest.mark.asyncio
async def test_water_intake_adds_cups(db_session: AsyncSession, test_user: User):
    """Test logging water intake adds cups for today."""
    result = await log_water(db_session, test_user.id, cups=8)

    assert result.cups == 8
    assert result.user_id == test_user.id


@pytest.mark.asyncio
async def test_water_intake_gets_today_total(db_session: AsyncSession, test_user: User):
    """Test getting water log returns today's total."""
    await log_water(db_session, test_user.id, cups=5)

    water_log = await get_water_log(db_session, test_user.id)

    assert water_log is not None
    assert water_log.cups == 5


@pytest.mark.asyncio
async def test_water_intake_upserts_for_same_day(
    db_session: AsyncSession, test_user: User
):
    """Test that logging water for the same day updates the value."""
    await log_water(db_session, test_user.id, cups=3)
    await log_water(db_session, test_user.id, cups=7)

    water_log = await get_water_log(db_session, test_user.id)

    assert water_log.cups == 7


@pytest.mark.asyncio
async def test_check_in_level_up_every_7_days(
    db_session: AsyncSession, test_user: User
):
    """Test that level increases every 7 days of streak."""
    habit_data = HabitCreate(
        name="Exercise", icon="fitness_center", plant_type="cactus"
    )
    habit = await create_habit(db_session, test_user.id, habit_data)

    today = date.today()
    for i in range(7):
        day = today - timedelta(days=6 - i)
        await check_in_habit(db_session, habit, day)

    await db_session.refresh(habit)

    assert habit.streak_days == 7
    assert habit.level == 1
