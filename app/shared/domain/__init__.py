"""Base domain exceptions for NutricIA.

All domain-level exceptions should inherit from DomainError.
These are caught at the presentation layer and mapped to HTTP responses.
"""


class DomainError(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


class NotFoundError(DomainError):
    """Entity was not found."""

    def __init__(self, entity: str = "Resource", identifier: str = ""):
        detail = f"{entity} not found"
        if identifier:
            detail = f"{entity} '{identifier}' not found"
        super().__init__(detail)


class UnauthorizedError(DomainError):
    """Authentication or authorization failure."""

    def __init__(self, message: str = "Not authorized"):
        super().__init__(message)


class ValidationError(DomainError):
    """Domain validation failure."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(message)


class ConflictError(DomainError):
    """Resource already exists or state conflict."""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message)
