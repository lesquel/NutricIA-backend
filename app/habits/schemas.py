from datetime import date
from typing import Literal

from pydantic import BaseModel


class HabitCreate(BaseModel):
    name: str
    icon: str = "eco"
    plant_type: str = "fern"  # fern | palm | mint | cactus


class HabitResponse(BaseModel):
    id: str
    name: str
    icon: str
    plant_type: str
    level: int
    streak_days: int
    plant_state: Literal["healthy", "growing", "wilted"]
    progress_percentage: float  # 0-100 within current level
    checked_today: bool

    model_config = {"from_attributes": True}


class HabitCheckInResponse(BaseModel):
    habit_id: str
    checked_at: date
    new_streak: int
    new_level: int


class WaterLogRequest(BaseModel):
    cups: int  # total cups for today (overwrite)


class WaterLogResponse(BaseModel):
    cups: int
    goal_cups: int
    date: date
