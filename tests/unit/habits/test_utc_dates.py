"""Tests that habit use-cases use UTC dates, not local date.today()."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.infrastructure.models import User
from app.habits.application.habit_use_cases import (
    check_in_habit,
    create_habit,
    is_checked_today,
    log_water,
)
from app.habits.presentation import HabitCreate


# Freeze "now" to a UTC midnight where UTC date differs from some local date
UTC_NOW = datetime(2026, 4, 15, 0, 30, 0, tzinfo=timezone.utc)
UTC_DATE = UTC_NOW.date()  # 2026-04-15


@pytest.mark.asyncio
async def test_check_in_habit_uses_utc_date(db_session: AsyncSession, test_user: User):
    """check_in_habit with no target_date should use UTC date, not date.today()."""
    data = HabitCreate(name="UTC test", icon="eco", plant_type="fern")
    habit = await create_habit(db_session, test_user.id, data)

    with patch(
        "app.habits.application.habit_use_cases.datetime",
    ) as mock_dt:
        mock_dt.now.return_value = UTC_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        await check_in_habit(db_session, habit)

    # The check-in date should be the UTC date
    from sqlalchemy import select
    from app.habits.infrastructure.models import HabitCheckIn

    result = await db_session.execute(
        select(HabitCheckIn).where(HabitCheckIn.habit_id == habit.id)
    )
    check_in = result.scalar_one()
    assert check_in.checked_at == UTC_DATE


@pytest.mark.asyncio
async def test_is_checked_today_uses_utc_date(
    db_session: AsyncSession, test_user: User
):
    """is_checked_today should compare against UTC date."""
    data = HabitCreate(name="UTC check", icon="eco", plant_type="fern")
    habit = await create_habit(db_session, test_user.id, data)

    # Check in for the UTC date
    await check_in_habit(db_session, habit, target_date=UTC_DATE)

    with patch(
        "app.habits.application.habit_use_cases.datetime",
    ) as mock_dt:
        mock_dt.now.return_value = UTC_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        checked = await is_checked_today(db_session, habit.id)

    assert checked is True


@pytest.mark.asyncio
async def test_log_water_uses_utc_date(db_session: AsyncSession, test_user: User):
    """log_water with no target_date should use UTC date."""
    with patch(
        "app.habits.application.habit_use_cases.datetime",
    ) as mock_dt:
        mock_dt.now.return_value = UTC_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        entry = await log_water(db_session, test_user.id, cups=5)

    assert entry.date == UTC_DATE
