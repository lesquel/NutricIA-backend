"""Analytics presentation — Pydantic schemas."""

from datetime import date

from pydantic import BaseModel


class DailySummary(BaseModel):
    date: date
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    meal_count: int
    calorie_goal: int
    goal_percentage: float  # 0-100+


class DailyAverage(BaseModel):
    avg_calories: float
    avg_protein: float
    avg_carbs: float
    avg_fat: float


class WeeklySummary(BaseModel):
    week_start: date
    week_end: date
    daily_averages: DailyAverage
    days: list[DailySummary]


class MonthlyData(BaseModel):
    month: str  # "2026-02"
    days: list[DailySummary]
    monthly_avg_calories: float
