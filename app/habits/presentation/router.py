"""Habits presentation — FastAPI router."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DB, CurrentUser
from app.habits.application.habit_use_cases import (
    check_in_habit,
    create_habit,
    get_user_habits,
    get_water_log,
    habit_to_response,
    log_water,
)
from app.habits.infrastructure.repository import delete_habit, get_habit_by_id_and_user
from app.habits.presentation import (
    HabitCheckInResponse,
    HabitCreate,
    HabitResponse,
    WaterLogRequest,
    WaterLogResponse,
)

router = APIRouter(prefix="/habits", tags=["habits"])


@router.get("", response_model=list[HabitResponse])
async def list_habits(user: CurrentUser, db: DB) -> list[HabitResponse]:
    """Get all habits for the current user."""
    habits = await get_user_habits(db, user.id)
    return [await habit_to_response(db, h) for h in habits]


@router.post("", response_model=HabitResponse, status_code=status.HTTP_201_CREATED)
async def add_habit(body: HabitCreate, user: CurrentUser, db: DB) -> HabitResponse:
    """Create a new habit (plant a seed)."""
    habit = await create_habit(db, user.id, body)
    return await habit_to_response(db, habit)


@router.post("/{habit_id}/check-in", response_model=HabitCheckInResponse)
async def do_check_in(
    habit_id: uuid.UUID, user: CurrentUser, db: DB
) -> HabitCheckInResponse:
    """Check in on a habit for today."""
    habit = await get_habit_by_id_and_user(db, habit_id, user.id)
    if habit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found"
        )

    new_streak, new_level = await check_in_habit(db, habit)
    return HabitCheckInResponse(
        habit_id=str(habit.id),
        checked_at=datetime.now(timezone.utc).date(),
        new_streak=new_streak,
        new_level=new_level,
    )


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_habit(habit_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    """Delete a habit."""
    habit = await get_habit_by_id_and_user(db, habit_id, user.id)
    if habit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found"
        )
    await delete_habit(db, habit)


# ── Water ─────────────────────────────────────


@router.post("/water", response_model=WaterLogResponse)
async def set_water(
    body: WaterLogRequest, user: CurrentUser, db: DB
) -> WaterLogResponse:
    """Set water intake (cups) for a date (defaults to today)."""
    entry = await log_water(db, user.id, body.cups, body.target_date)
    goal_cups = round(max(user.water_goal_ml, 1) / 250)  # ~250ml per cup
    return WaterLogResponse(cups=entry.cups, goal_cups=goal_cups, date=entry.date)


@router.get("/water", response_model=WaterLogResponse)
async def get_water(
    user: CurrentUser,
    db: DB,
    target_date: date | None = None,
) -> WaterLogResponse:
    """Get water intake for a given date."""
    entry = await get_water_log(db, user.id, target_date)
    goal_cups = round(max(user.water_goal_ml, 1) / 250)
    return WaterLogResponse(
        cups=entry.cups if entry else 0,
        goal_cups=goal_cups,
        date=target_date or datetime.now(timezone.utc).date(),
    )
