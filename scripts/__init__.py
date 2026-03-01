"""
Seed script for NutricIA — populates the database with realistic test data.

Usage:
    cd backend/
    uv run python -m scripts.seed          # seed the database
    uv run python -m scripts.seed --reset  # drop all data and re-seed
"""

import asyncio
import json
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

# ── Bootstrap ----------------------------------------------------------------
from app.shared.infrastructure import Base, async_session, engine
from app.auth.infrastructure.models import User
from app.meals.infrastructure import Meal, MealTag
from app.habits.infrastructure import Habit, HabitCheckIn, WaterIntake

# ── Seed Data -----------------------------------------------------------------

USERS = [
    {
        "email": "jane@nutricia.dev",
        "name": "Jane Doe",
        "password": "test1234",
        "calorie_goal": 2100,
        "water_goal_ml": 2500,
        "dietary_preferences": json.dumps(["Vegan", "Low Sugar"]),
    },
    {
        "email": "alex@nutricia.dev",
        "name": "Alex García",
        "password": "test1234",
        "calorie_goal": 2200,
        "water_goal_ml": 2000,
        "dietary_preferences": json.dumps(["Mediterranean"]),
    },
]


def _dt(days_ago: int = 0, hour: int = 12, minute: int = 0) -> datetime:
    """Return a timezone-aware datetime relative to today."""
    d = date.today() - timedelta(days=days_ago)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)


MEALS_JANE = [
    # Today
    dict(name="Avocado Toast", calories=350, protein_g=12, carbs_g=30, fat_g=22, meal_type="breakfast", logged_at=_dt(0, 8, 30), tags=["High Fiber", "Vegan"]),
    dict(name="Black Coffee", calories=5, protein_g=0.3, carbs_g=0, fat_g=0, meal_type="breakfast", logged_at=_dt(0, 8, 35), tags=[]),
    dict(name="Quinoa Buddha Bowl", calories=480, protein_g=18, carbs_g=55, fat_g=20, meal_type="lunch", logged_at=_dt(0, 12, 45), tags=["Vegan", "Protein"]),
    dict(name="Raw Almonds", calories=150, protein_g=6, carbs_g=5, fat_g=13, meal_type="snack", logged_at=_dt(0, 16, 0), tags=["Protein"]),
    dict(name="Grilled Salmon", calories=620, protein_g=42, carbs_g=12, fat_g=35, meal_type="dinner", logged_at=_dt(0, 19, 0), tags=["Omega-3"]),
    # Yesterday
    dict(name="Smoothie Bowl", calories=310, protein_g=10, carbs_g=48, fat_g=8, meal_type="breakfast", logged_at=_dt(1, 7, 45), tags=["Antioxidant"]),
    dict(name="Lentil Soup", calories=380, protein_g=22, carbs_g=45, fat_g=8, meal_type="lunch", logged_at=_dt(1, 13, 0), tags=["High Fiber"]),
    dict(name="Greek Yogurt", calories=120, protein_g=15, carbs_g=10, fat_g=2, meal_type="snack", logged_at=_dt(1, 15, 30), tags=["Protein"]),
    dict(name="Veggie Stir Fry", calories=350, protein_g=14, carbs_g=40, fat_g=14, meal_type="dinner", logged_at=_dt(1, 19, 30), tags=["Vegan"]),
    # 2 days ago
    dict(name="Oatmeal with Berries", calories=280, protein_g=8, carbs_g=50, fat_g=6, meal_type="breakfast", logged_at=_dt(2, 8, 0), tags=["Whole Grain"]),
    dict(name="Caesar Salad", calories=420, protein_g=28, carbs_g=18, fat_g=28, meal_type="lunch", logged_at=_dt(2, 12, 30), tags=[]),
    dict(name="Banana", calories=105, protein_g=1.3, carbs_g=27, fat_g=0.4, meal_type="snack", logged_at=_dt(2, 15, 0), tags=["Quick Energy"]),
    dict(name="Pasta Primavera", calories=520, protein_g=16, carbs_g=70, fat_g=18, meal_type="dinner", logged_at=_dt(2, 19, 0), tags=[]),
    # 3 days ago
    dict(name="Eggs Benedict", calories=450, protein_g=24, carbs_g=30, fat_g=30, meal_type="breakfast", logged_at=_dt(3, 9, 0), tags=["Protein"]),
    dict(name="Tuna Wrap", calories=380, protein_g=30, carbs_g=35, fat_g=12, meal_type="lunch", logged_at=_dt(3, 12, 0), tags=["Omega-3"]),
    dict(name="Trail Mix", calories=220, protein_g=7, carbs_g=20, fat_g=14, meal_type="snack", logged_at=_dt(3, 16, 0), tags=[]),
    dict(name="Chicken Breast with Rice", calories=550, protein_g=45, carbs_g=50, fat_g=12, meal_type="dinner", logged_at=_dt(3, 20, 0), tags=["High Protein"]),
]

MEALS_ALEX = [
    dict(name="Scrambled Eggs", calories=300, protein_g=20, carbs_g=4, fat_g=22, meal_type="breakfast", logged_at=_dt(0, 7, 0), tags=["Keto"]),
    dict(name="Chicken Gyro", calories=520, protein_g=35, carbs_g=40, fat_g=22, meal_type="lunch", logged_at=_dt(0, 13, 0), tags=["Mediterranean"]),
    dict(name="Apple with PB", calories=250, protein_g=7, carbs_g=30, fat_g=14, meal_type="snack", logged_at=_dt(0, 16, 30), tags=[]),
    dict(name="Grilled Fish Tacos", calories=480, protein_g=30, carbs_g=35, fat_g=22, meal_type="dinner", logged_at=_dt(0, 19, 30), tags=["Omega-3"]),
    dict(name="Pancakes", calories=450, protein_g=10, carbs_g=55, fat_g=20, meal_type="breakfast", logged_at=_dt(1, 8, 30), tags=[]),
    dict(name="Falafel Plate", calories=600, protein_g=20, carbs_g=65, fat_g=28, meal_type="lunch", logged_at=_dt(1, 12, 0), tags=["Mediterranean"]),
]

HABITS_JANE = [
    dict(name="Calorie Balance", icon="eco", plant_type="fern", level=3, streak_days=5),
    dict(name="Protein Goal", icon="fitness-center", plant_type="palm", level=1, streak_days=2),
    dict(name="No Sugar", icon="block", plant_type="mint", level=2, streak_days=0),
]

HABITS_ALEX = [
    dict(name="Drink Water", icon="water-drop", plant_type="cactus", level=4, streak_days=8),
    dict(name="Eat Vegetables", icon="eco", plant_type="fern", level=2, streak_days=3),
]

# ── Logic ---------------------------------------------------------------------


async def seed(session: AsyncSession, reset: bool = False) -> None:
    if reset:
        print("🗑  Dropping all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("📦 Re-creating tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        # Ensure tables exist (idempotent)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ── Users ──────────────────────────────────────────────────────────────
    print("👤 Seeding users...")
    user_ids: dict[str, uuid.UUID] = {}
    for u in USERS:
        user = User(
            email=u["email"],
            name=u["name"],
            password_hash=bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode(),
            calorie_goal=u["calorie_goal"],
            water_goal_ml=u["water_goal_ml"],
            dietary_preferences=u["dietary_preferences"],
        )
        session.add(user)
        await session.flush()
        user_ids[u["email"]] = user.id
        print(f"   ✓ {u['name']} ({u['email']})  id={user.id}")

    jane_id = user_ids["jane@nutricia.dev"]
    alex_id = user_ids["alex@nutricia.dev"]

    # ── Meals ──────────────────────────────────────────────────────────────
    print("🍽  Seeding meals...")
    for meal_data in MEALS_JANE:
        tags = meal_data.pop("tags")
        meal = Meal(user_id=jane_id, confidence_score=0.92, **meal_data)
        meal.tags = [MealTag(label=t) for t in tags]
        session.add(meal)

    for meal_data in MEALS_ALEX:
        tags = meal_data.pop("tags")
        meal = Meal(user_id=alex_id, confidence_score=0.88, **meal_data)
        meal.tags = [MealTag(label=t) for t in tags]
        session.add(meal)

    print(f"   ✓ {len(MEALS_JANE)} meals for Jane, {len(MEALS_ALEX)} for Alex")

    # ── Habits ─────────────────────────────────────────────────────────────
    print("🌱 Seeding habits...")
    for h in HABITS_JANE:
        habit = Habit(user_id=jane_id, **h)
        session.add(habit)
        await session.flush()
        # Add check-ins for the streak
        for i in range(h["streak_days"]):
            session.add(
                HabitCheckIn(
                    habit_id=habit.id,
                    checked_at=date.today() - timedelta(days=i),
                )
            )

    for h in HABITS_ALEX:
        habit = Habit(user_id=alex_id, **h)
        session.add(habit)
        await session.flush()
        for i in range(h["streak_days"]):
            session.add(
                HabitCheckIn(
                    habit_id=habit.id,
                    checked_at=date.today() - timedelta(days=i),
                )
            )

    print(f"   ✓ {len(HABITS_JANE)} habits for Jane, {len(HABITS_ALEX)} for Alex")

    # ── Water Intake ───────────────────────────────────────────────────────
    print("💧 Seeding water intake...")
    for days_ago in range(7):
        d = date.today() - timedelta(days=days_ago)
        cups_jane = max(0, 8 - days_ago)  # Today = 8, yesterday = 7 ...
        cups_alex = max(0, 6 - days_ago)
        session.add(WaterIntake(user_id=jane_id, cups=cups_jane, date=d))
        session.add(WaterIntake(user_id=alex_id, cups=cups_alex, date=d))

    print("   ✓ 7 days of water intake per user")

    await session.commit()
    print("\n✅ Seed complete!")
    print("   Login → jane@nutricia.dev / test1234")
    print("   Login → alex@nutricia.dev / test1234")


async def main() -> None:
    reset = "--reset" in sys.argv
    async with async_session() as session:
        await seed(session, reset=reset)


if __name__ == "__main__":
    asyncio.run(main())
