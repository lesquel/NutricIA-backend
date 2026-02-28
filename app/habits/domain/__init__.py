"""Habits domain — value objects."""

from enum import StrEnum


class PlantType(StrEnum):
    FERN = "fern"
    PALM = "palm"
    MINT = "mint"
    CACTUS = "cactus"


class PlantState(StrEnum):
    HEALTHY = "healthy"
    GROWING = "growing"
    WILTED = "wilted"
