"""Meal plans infrastructure — LLM-based plan generator with constraint retry loop."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.meal_plans.domain.entities import (
    DietaryConstraints,
    Macros,
    MealPlan,
    MealType,
    PlannedMeal,
)

logger = logging.getLogger(__name__)

# ── Pydantic schemas for LLM tool binding ────────────────────────────────────


class RecipeCardSchema(BaseModel):
    """A single planned meal inside a day."""

    meal_type: str = Field(description="One of: breakfast, lunch, snack, dinner")
    recipe_name: str = Field(description="Name of the recipe")
    recipe_ingredients: list[str] = Field(description="List of ingredient strings")
    calories: float = Field(description="Total calories for one serving", gt=0)
    protein_g: float = Field(description="Protein in grams", ge=0)
    carbs_g: float = Field(description="Carbohydrates in grams", ge=0)
    fat_g: float = Field(description="Fat in grams", ge=0)
    cook_time_minutes: int | None = Field(
        default=None, description="Approximate cook time in minutes"
    )
    difficulty: str | None = Field(
        default=None, description="One of: easy, medium, hard"
    )
    servings: int = Field(default=1, description="Number of servings", ge=1)


class DayPlanSchema(BaseModel):
    """All meals for a single day of the week."""

    day_of_week: int = Field(description="0=Monday ... 6=Sunday", ge=0, le=6)
    meals: list[RecipeCardSchema] = Field(description="3-4 meals for the day")


class WeeklyPlanSchema(BaseModel):
    """Full 7-day meal plan."""

    days: list[DayPlanSchema] = Field(description="7 days, one entry per day")


# ── Prompt builder ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are NutricIA, an expert nutritionist and meal planner specializing in Ecuadorian and \
Latin American cuisine. Generate a complete 7-day meal plan (days 0-6, Monday to Sunday) \
with 3-4 meals per day.

IMPORTANT RULES:
- Each day must hit the target calories WITHIN ±10% tolerance.
- Macro ratios (protein/carbs/fat) must match the target ratios provided.
- Use culturally appropriate Ecuadorian and regional ingredients where possible \
  (mote, plátano maduro, tostado, fritada, llapingachos, seco de pollo, etc.).
- Respect ALL dietary constraints strictly.
- Vary recipes across days — do not repeat the same meal twice in a week.
- Provide realistic ingredient lists and cook times.
"""


def _build_plan_prompt(
    target_calories: int,
    target_macros: Macros,
    constraints: DietaryConstraints,
    context: dict[str, Any],
    feedback: str | None = None,
) -> str:
    dietary_notes: list[str] = []
    if constraints.vegetarian:
        dietary_notes.append("VEGETARIAN — no meat, no poultry, no seafood")
    if constraints.vegan:
        dietary_notes.append("VEGAN — no animal products of any kind")
    if constraints.gluten_free:
        dietary_notes.append("GLUTEN-FREE — no wheat, barley, rye")
    if constraints.allergies:
        dietary_notes.append(f"ALLERGIES: {', '.join(constraints.allergies)}")

    frequent_foods = context.get("frequent_foods", [])
    frequent_note = (
        f"The user frequently eats: {', '.join(frequent_foods[:10])}."
        if frequent_foods
        else ""
    )

    prompt_parts = [
        f"Target: {target_calories} kcal/day (±10% tolerance per day).",
        f"Macro targets: protein {target_macros.protein_g:.0f}g, "
        f"carbs {target_macros.carbs_g:.0f}g, fat {target_macros.fat_g:.0f}g per day.",
    ]

    if dietary_notes:
        prompt_parts.append("Dietary constraints: " + "; ".join(dietary_notes))

    if frequent_note:
        prompt_parts.append(frequent_note)

    if feedback:
        prompt_parts.append(f"\nCORRECTION NEEDED: {feedback}")
        prompt_parts.append(
            "Please regenerate the FULL 7-day plan correcting the issues above."
        )

    prompt_parts.append(
        "\nRespond with a valid JSON object matching the WeeklyPlanSchema. "
        "No markdown fences, no extra text."
    )

    return "\n".join(prompt_parts)


def _build_single_meal_prompt(
    day_of_week: int,
    meal_type: str,
    target_calories: int,
    target_macros: Macros,
    constraints: DietaryConstraints,
    context: dict[str, Any],
) -> str:
    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    day_name = day_names[day_of_week]

    dietary_notes: list[str] = []
    if constraints.vegetarian:
        dietary_notes.append("VEGETARIAN")
    if constraints.vegan:
        dietary_notes.append("VEGAN")
    if constraints.gluten_free:
        dietary_notes.append("GLUTEN-FREE")
    if constraints.allergies:
        dietary_notes.append(f"Allergies: {', '.join(constraints.allergies)}")

    per_meal_calories = target_calories // 4  # rough estimate for one meal

    parts = [
        f"Generate a single {meal_type} meal for {day_name}.",
        f"Target approximately {per_meal_calories} kcal.",
        f"Macro reference: protein {target_macros.protein_g / 4:.0f}g, "
        f"carbs {target_macros.carbs_g / 4:.0f}g, fat {target_macros.fat_g / 4:.0f}g.",
    ]
    if dietary_notes:
        parts.append("Constraints: " + "; ".join(dietary_notes))

    frequent_foods = context.get("frequent_foods", [])
    if frequent_foods:
        parts.append(f"User frequently eats: {', '.join(frequent_foods[:5])}")

    parts.append(
        "\nRespond with a single RecipeCardSchema JSON object. No markdown, no extra text."
    )
    return "\n".join(parts)


# ── LLM helpers ──────────────────────────────────────────────────────────────


def _extract_json(text: str) -> Any:
    """Extract first JSON object from possibly-noisy LLM output."""
    text = text.strip()
    if text.startswith("```"):
        inner = text.split("\n", 1)[1] if "\n" in text else text[3:]
        inner = inner[:-3] if inner.endswith("```") else inner
        text = inner.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch in ("{", "["):
            try:
                parsed, _ = decoder.raw_decode(text[idx:])
                return parsed
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Cannot parse JSON from LLM output: {text[:200]}")


def _get_llm() -> Any:
    """Instantiate the primary LLM.

    Provider priority respects ``settings.ai_provider`` when credentials are
    available, otherwise falls back to the first provider with credentials in
    this order: groq → gemini → openai. Returns ``None`` if nothing is
    configured (mock path).
    """
    if settings.ai_provider == "mock":
        return None  # handled by mock path

    # Ordered candidates: configured primary first, then groq → gemini → openai
    candidates: list[str] = []
    if settings.ai_provider not in ("mock", ""):
        candidates.append(settings.ai_provider)
    for name in ("groq", "gemini", "openai"):
        if name not in candidates:
            candidates.append(name)

    for provider in candidates:
        try:
            if provider == "groq" and settings.groq_api_key:
                from langchain_groq import ChatGroq
                from pydantic import SecretStr

                return ChatGroq(  # type: ignore[call-arg]
                    model=(
                        settings.ai_model
                        if settings.ai_provider == "groq" and settings.ai_model
                        else "meta-llama/llama-4-scout-17b-16e-instruct"
                    ),
                    temperature=0.3,
                    max_tokens=4096,
                    api_key=SecretStr(settings.groq_api_key),
                )

            if provider == "gemini" and settings.google_api_key:
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(
                    model=(
                        settings.ai_model
                        if settings.ai_provider == "gemini" and settings.ai_model
                        else "gemini-2.0-flash"
                    ),
                    temperature=0.3,
                    max_output_tokens=4096,
                    google_api_key=settings.google_api_key or None,
                )

            if provider == "openai" and settings.openai_api_key:
                from langchain_openai import ChatOpenAI
                from pydantic import SecretStr

                return ChatOpenAI(
                    model=(
                        settings.ai_model
                        if settings.ai_provider == "openai" and settings.ai_model
                        else "gpt-4o"
                    ),
                    temperature=0.3,
                    api_key=SecretStr(settings.openai_api_key),
                )
        except Exception as exc:
            logger.warning("%s unavailable for plan generation: %s", provider, exc)

    return None


# ── Validation ────────────────────────────────────────────────────────────────


def _validate_plan_macros(
    plan: MealPlan,
    target_calories: int,
    tolerance: float = 0.10,
) -> list[str]:
    """Return list of feedback messages for days outside ±tolerance of target_calories."""
    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    issues: list[str] = []
    lower = target_calories * (1 - tolerance)
    upper = target_calories * (1 + tolerance)
    for day in range(7):
        daily = plan.daily_calories(day)
        if daily == 0:
            continue  # no meals planned for this day — skip
        if not (lower <= daily <= upper):
            issues.append(
                f"Day {day_names[day]} had {daily:.0f} kcal, "
                f"target {target_calories} ±{int(target_calories * tolerance)}. Adjust."
            )
    return issues


# ── Plan parser ───────────────────────────────────────────────────────────────


def _parse_weekly_plan(
    raw: Any,
    plan_id: uuid.UUID,
    user_id: uuid.UUID,
    week_start: date,
) -> MealPlan:
    schema = WeeklyPlanSchema.model_validate(raw)
    meals: list[PlannedMeal] = []
    for day in schema.days:
        for recipe in day.meals:
            meal_type: MealType = (
                recipe.meal_type
                if recipe.meal_type
                in (  # type: ignore[assignment]
                    "breakfast",
                    "lunch",
                    "snack",
                    "dinner",
                )
                else "snack"
            )
            difficulty = (
                recipe.difficulty
                if recipe.difficulty in ("easy", "medium", "hard")
                else None
            )
            meals.append(
                PlannedMeal(
                    id=uuid.uuid4(),
                    plan_id=plan_id,
                    day_of_week=day.day_of_week,
                    meal_type=meal_type,
                    recipe_name=recipe.recipe_name,
                    recipe_ingredients=recipe.recipe_ingredients,
                    calories=recipe.calories,
                    macros=Macros(
                        protein_g=recipe.protein_g,
                        carbs_g=recipe.carbs_g,
                        fat_g=recipe.fat_g,
                    ),
                    cook_time_minutes=recipe.cook_time_minutes,
                    difficulty=difficulty,  # type: ignore[arg-type]
                    servings=recipe.servings,
                    is_logged=False,
                    logged_meal_id=None,
                )
            )
    return MealPlan(
        id=plan_id,
        user_id=user_id,
        week_start=week_start,
        target_calories=0,  # filled in by caller
        target_macros=Macros(protein_g=0, carbs_g=0, fat_g=0),  # filled in by caller
        status="active",
        approximation=False,
        meals=meals,
    )


# ── Generator ────────────────────────────────────────────────────────────────


class LLMPlanGenerator:
    """Implements PlanGeneratorPort using Groq primary, with Gemini/OpenAI fallback.

    Includes a constraint validation loop: if any day's calories deviate more than
    10% from the target, one retry (up to MAX_RETRIES) is attempted with feedback.
    If retries are exhausted, the plan is returned with ``approximation=True``.
    """

    MAX_RETRIES = 2

    def __init__(self) -> None:
        self._llm = _get_llm()

    async def generate(
        self,
        user_id: uuid.UUID,
        target_calories: int,
        target_macros: Macros,
        constraints: DietaryConstraints,
        context: dict[str, Any],
        week_start: date | None = None,
    ) -> MealPlan:
        if week_start is None:
            today = date.today()
            # Monday of current week
            week_start = today  # caller should pass correct date; use today as fallback

        plan_id = uuid.uuid4()

        if self._llm is None:
            # Mock path: return deterministic plan for dev/test
            return self._mock_generate(
                plan_id, user_id, week_start, target_calories, target_macros
            )

        feedback: str | None = None
        plan: MealPlan | None = None
        attempt = 0

        while attempt <= self.MAX_RETRIES:
            prompt = _build_plan_prompt(
                target_calories, target_macros, constraints, context, feedback
            )
            logger.info(
                "LLMPlanGenerator: attempt %d for user %s", attempt + 1, user_id
            )

            try:
                from langchain_core.messages import HumanMessage, SystemMessage

                response = await self._llm.ainvoke(
                    [
                        SystemMessage(content=_SYSTEM_PROMPT),
                        HumanMessage(content=prompt),
                    ]
                )
                text = (
                    response.content
                    if isinstance(response.content, str)
                    else str(response.content)
                )
                raw = _extract_json(text)
                plan = _parse_weekly_plan(raw, plan_id, user_id, week_start)
                # Inject targets onto plan (they were zeroed in parser)
                plan = MealPlan(
                    id=plan.id,
                    user_id=plan.user_id,
                    week_start=plan.week_start,
                    target_calories=target_calories,
                    target_macros=target_macros,
                    status="active",
                    approximation=False,
                    meals=plan.meals,
                )
            except Exception as exc:
                logger.warning(
                    "LLMPlanGenerator: LLM error on attempt %d: %s", attempt + 1, exc
                )
                attempt += 1
                if attempt > self.MAX_RETRIES:
                    raise
                continue

            issues = _validate_plan_macros(plan, target_calories)
            if not issues:
                logger.info(
                    "LLMPlanGenerator: plan passed validation on attempt %d",
                    attempt + 1,
                )
                return plan

            feedback = " | ".join(issues)
            logger.warning(
                "LLMPlanGenerator: attempt %d failed validation: %s",
                attempt + 1,
                feedback,
            )
            attempt += 1

        # Exceeded retries — return with approximation flag
        if plan is not None:
            logger.warning(
                "LLMPlanGenerator: returning plan with approximation=True after %d retries",
                self.MAX_RETRIES,
            )
            return MealPlan(
                id=plan.id,
                user_id=plan.user_id,
                week_start=plan.week_start,
                target_calories=target_calories,
                target_macros=target_macros,
                status="active",
                approximation=True,
                meals=plan.meals,
            )

        raise RuntimeError("LLMPlanGenerator: exhausted retries with no plan generated")

    async def generate_single_meal(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        day_of_week: int,
        meal_type: str,
        target_calories: int,
        target_macros: Macros,
        constraints: DietaryConstraints,
        context: dict[str, Any],
    ) -> PlannedMeal:
        """Generate a single replacement meal (for swap)."""
        if self._llm is None:
            return self._mock_single_meal(plan_id, day_of_week, meal_type)

        prompt = _build_single_meal_prompt(
            day_of_week, meal_type, target_calories, target_macros, constraints, context
        )

        from langchain_core.messages import HumanMessage, SystemMessage

        response = await self._llm.ainvoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        text = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )
        raw = _extract_json(text)
        recipe = RecipeCardSchema.model_validate(raw)
        meal_type_validated: MealType = (
            recipe.meal_type
            if recipe.meal_type
            in (  # type: ignore[assignment]
                "breakfast",
                "lunch",
                "snack",
                "dinner",
            )
            else "snack"
        )
        difficulty = (
            recipe.difficulty
            if recipe.difficulty in ("easy", "medium", "hard")
            else None
        )

        return PlannedMeal(
            id=uuid.uuid4(),
            plan_id=plan_id,
            day_of_week=day_of_week,
            meal_type=meal_type_validated,
            recipe_name=recipe.recipe_name,
            recipe_ingredients=recipe.recipe_ingredients,
            calories=recipe.calories,
            macros=Macros(
                protein_g=recipe.protein_g,
                carbs_g=recipe.carbs_g,
                fat_g=recipe.fat_g,
            ),
            cook_time_minutes=recipe.cook_time_minutes,
            difficulty=difficulty,  # type: ignore[arg-type]
            servings=recipe.servings,
            is_logged=False,
            logged_meal_id=None,
        )

    # ── Mock paths (dev / test) ───────────────────────────────────────────────

    def _mock_generate(
        self,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
        week_start: date,
        target_calories: int,
        target_macros: Macros,
    ) -> MealPlan:
        """Return a deterministic 7-day plan for dev/test without an LLM."""
        meals: list[PlannedMeal] = []
        meal_types: list[MealType] = ["breakfast", "lunch", "snack", "dinner"]
        per_meal_cal = target_calories / 4

        for day in range(7):
            for i, mt in enumerate(meal_types):
                meals.append(
                    PlannedMeal(
                        id=uuid.uuid4(),
                        plan_id=plan_id,
                        day_of_week=day,
                        meal_type=mt,
                        recipe_name=f"Mock {mt.capitalize()} Day {day}",
                        recipe_ingredients=["ingredient1", "ingredient2"],
                        calories=per_meal_cal,
                        macros=Macros(
                            protein_g=target_macros.protein_g / 4,
                            carbs_g=target_macros.carbs_g / 4,
                            fat_g=target_macros.fat_g / 4,
                        ),
                        cook_time_minutes=20,
                        difficulty="easy",
                        servings=1,
                        is_logged=False,
                        logged_meal_id=None,
                    )
                )

        return MealPlan(
            id=plan_id,
            user_id=user_id,
            week_start=week_start,
            target_calories=target_calories,
            target_macros=target_macros,
            status="active",
            approximation=False,
            meals=meals,
        )

    def _mock_single_meal(
        self,
        plan_id: uuid.UUID,
        day_of_week: int,
        meal_type: str,
    ) -> PlannedMeal:
        meal_type_val: MealType = (
            meal_type
            if meal_type
            in (  # type: ignore[assignment]
                "breakfast",
                "lunch",
                "snack",
                "dinner",
            )
            else "snack"
        )
        return PlannedMeal(
            id=uuid.uuid4(),
            plan_id=plan_id,
            day_of_week=day_of_week,
            meal_type=meal_type_val,
            recipe_name=f"Mock Swap {meal_type.capitalize()}",
            recipe_ingredients=["ingredient1", "ingredient2"],
            calories=500.0,
            macros=Macros(protein_g=30, carbs_g=50, fat_g=15),
            cook_time_minutes=15,
            difficulty="easy",
            servings=1,
            is_logged=False,
            logged_meal_id=None,
        )
