"""Catalog data source — Open Food Facts."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.catalog.domain.entities import FoodCatalogEntry

logger = logging.getLogger("nutricia.catalog.openfoodfacts")

_OFF_SEARCH_URL = (
    "https://world.openfoodfacts.org/cgi/search.pl"
    "?action=process&sort_by=popularity&page_size=200&json=true"
)
_TIMEOUT = 20.0


class OpenFoodFactsSource:
    """Fetches popular products from the Open Food Facts API.

    The API is public and requires no API key.  On any error the source
    logs a warning and returns an empty list (graceful degradation).
    """

    async def fetch(self) -> list[FoodCatalogEntry]:
        """Fetch top ~200 popular products from Open Food Facts."""
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed — skipping Open Food Facts source")
            return []

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(_OFF_SEARCH_URL)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except Exception as exc:
            logger.warning("Open Food Facts API error: %s — skipping source", exc)
            return []

        products: list[dict[str, Any]] = data.get("products", [])
        entries: list[FoodCatalogEntry] = []
        for product in products:
            entry = _normalize_off(product)
            if entry is not None:
                entries.append(entry)

        logger.info("Open Food Facts source fetched %d entries", len(entries))
        return entries


def _normalize_off(product: dict[str, Any]) -> FoodCatalogEntry | None:
    """Convert an Open Food Facts product to a FoodCatalogEntry."""
    name = (product.get("product_name_en") or product.get("product_name") or "").strip()
    if not name:
        return None

    # Nutriments per 100g
    nutriments: dict[str, Any] = product.get("nutriments", {})

    def _safe_float(key: str) -> float:
        val = nutriments.get(key, 0.0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    macros: dict[str, Any] = {
        "calories": _safe_float("energy-kcal_100g"),
        "protein_g": _safe_float("proteins_100g"),
        "carbs_g": _safe_float("carbohydrates_100g"),
        "fat_g": _safe_float("fat_100g"),
    }

    # Optional
    fiber = _safe_float("fiber_100g")
    if fiber:
        macros["fiber_g"] = fiber

    sugar = _safe_float("sugars_100g")
    if sugar:
        macros["sugar_g"] = sugar

    sodium = _safe_float("sodium_100g")
    if sodium:
        macros["sodium_mg"] = sodium * 1000  # g → mg

    # Collect aliases from alternate name fields
    aliases: list[str] = []
    for field in ("generic_name", "product_name_fr", "product_name_es"):
        alt = product.get(field, "").strip()
        if alt and alt != name:
            aliases.append(alt)

    return FoodCatalogEntry(
        id=uuid.uuid4(),
        canonical_name=name,
        aliases=aliases,
        macros_per_100g=macros,
        source="openfoodfacts",
    )
