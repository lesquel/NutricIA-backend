"""Catalog domain entities."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FoodCatalogEntry:
    """A canonical food item in the catalog.

    Attributes
    ----------
    id:
        Unique identifier (UUID).
    canonical_name:
        The normalised name (e.g. "Chicken Breast", "Brown Rice").
    aliases:
        Alternative names used for search / display.
    macros_per_100g:
        Nutritional values per 100 g.  Expected keys: calories, protein_g,
        carbs_g, fat_g.  Optional: fiber_g, sugar_g, sodium_mg, etc.
    source:
        Data provenance: 'usda' | 'openfoodfacts' | 'ecuador_curated' | 'user_generated'.
    created_at:
        Timestamp of first insertion (optional, set by DB).
    """

    id: uuid.UUID
    canonical_name: str
    aliases: list[str]
    macros_per_100g: dict
    source: str
    created_at: datetime | None = field(default=None)
