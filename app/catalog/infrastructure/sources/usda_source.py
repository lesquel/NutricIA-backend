"""Catalog data source — USDA FoodData Central."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.catalog.domain.entities import FoodCatalogEntry

logger = logging.getLogger("nutricia.catalog.usda")

_USDA_API_BASE = "https://api.nal.usda.gov/fdc/v1/foods/list"
_PAGE_SIZE = 200
_MAX_PAGES = 3  # Up to 600 entries for v1


class UsdaSource:
    """Fetches food data from USDA FoodData Central API.

    Requires USDA_API_KEY in settings.  If the key is missing or the API
    returns an error, the source logs a warning and returns an empty list
    (graceful degradation).
    """

    async def fetch(self) -> list[FoodCatalogEntry]:
        """Fetch Foundation and SR Legacy foods from USDA FDC API."""
        from app.config import settings

        api_key: str = getattr(settings, "usda_api_key", "")
        if not api_key:
            logger.warning("USDA_API_KEY not configured — skipping USDA source")
            return []

        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed — skipping USDA source")
            return []

        entries: list[FoodCatalogEntry] = []
        for page in range(1, _MAX_PAGES + 1):
            try:
                params: dict[str, Any] = {
                    "api_key": api_key,
                    "dataType": "Foundation,SR Legacy",
                    "pageSize": _PAGE_SIZE,
                    "pageNumber": page,
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(_USDA_API_BASE, params=params)
                    response.raise_for_status()
                    foods: list[dict[str, Any]] = response.json()

                if not foods:
                    break  # No more pages

                for food in foods:
                    entry = _normalize_usda(food)
                    if entry is not None:
                        entries.append(entry)

            except Exception as exc:
                logger.warning(
                    "USDA API error on page %d: %s — skipping remaining pages",
                    page,
                    exc,
                )
                break

        logger.info("USDA source fetched %d entries", len(entries))
        return entries


def _normalize_usda(food: dict[str, Any]) -> FoodCatalogEntry | None:
    """Convert a USDA food item dict to a FoodCatalogEntry."""
    name = food.get("description", "").strip()
    if not name:
        return None

    # Extract macros from nutrients list
    nutrients = {
        n.get("name", ""): n.get("amount", 0.0) for n in food.get("foodNutrients", [])
    }

    macros: dict[str, Any] = {
        "calories": nutrients.get("Energy", 0.0),
        "protein_g": nutrients.get("Protein", 0.0),
        "carbs_g": nutrients.get("Carbohydrate, by difference", 0.0),
        "fat_g": nutrients.get("Total lipid (fat)", 0.0),
    }

    # Optional fields
    if "Fiber, total dietary" in nutrients:
        macros["fiber_g"] = nutrients["Fiber, total dietary"]
    if "Sugars, total including NLEA" in nutrients:
        macros["sugar_g"] = nutrients["Sugars, total including NLEA"]
    if "Sodium, Na" in nutrients:
        macros["sodium_mg"] = nutrients["Sodium, Na"]

    return FoodCatalogEntry(
        id=uuid.uuid4(),
        canonical_name=name,
        aliases=[],
        macros_per_100g=macros,
        source="usda",
    )
