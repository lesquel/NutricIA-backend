"""Catalog data source — Ecuador curated foods."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from app.catalog.domain.entities import FoodCatalogEntry

logger = logging.getLogger("nutricia.catalog.ecuador")

_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "ecuador_foods.json"


class EcuadorSource:
    """Reads hand-curated Ecuadorian food entries from a local JSON file."""

    async def fetch(self) -> list[FoodCatalogEntry]:
        """Load and return Ecuadorian food entries from the bundled JSON file."""
        try:
            with _DATA_FILE.open(encoding="utf-8") as fh:
                raw: list[dict] = json.load(fh)
        except FileNotFoundError:
            logger.warning("Ecuador foods data file not found: %s", _DATA_FILE)
            return []
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse Ecuador foods JSON: %s", exc)
            return []

        entries: list[FoodCatalogEntry] = []
        for item in raw:
            try:
                entry = FoodCatalogEntry(
                    id=uuid.uuid4(),
                    canonical_name=item["canonical_name"],
                    aliases=item.get("aliases", []),
                    macros_per_100g=item.get("macros_per_100g", {}),
                    source="ecuador",
                )
                entries.append(entry)
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed Ecuador entry: %s — %s", item, exc)

        logger.info("Ecuador source loaded %d entries", len(entries))
        return entries
