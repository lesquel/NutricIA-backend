"""Catalog domain errors."""

from app.shared.domain import ConflictError, NotFoundError


class CatalogEntryNotFoundError(NotFoundError):
    """Raised when a food catalog entry is not found."""

    def __init__(self, identifier: str = "") -> None:
        super().__init__(entity="FoodCatalogEntry", identifier=identifier)


class DuplicateCanonicalNameError(ConflictError):
    """Raised when a (canonical_name, source) pair already exists."""

    def __init__(self, canonical_name: str, source: str) -> None:
        super().__init__(
            message=f"FoodCatalogEntry '{canonical_name}' from source '{source}' already exists."
        )
