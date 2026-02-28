"""Auth domain — value objects and exceptions."""

from enum import StrEnum


class AuthMethod(StrEnum):
    """Supported authentication methods."""
    EMAIL = "email"
    GOOGLE = "google"
    APPLE = "apple"


# Backward-compatible alias
OAuthProvider = AuthMethod


class InvalidTokenError(Exception):
    """Raised when an OAuth token is invalid."""

    def __init__(self, message: str = "Invalid token"):
        self.message = message
        super().__init__(self.message)


class InvalidCredentialsError(Exception):
    """Raised when email/password credentials are wrong."""

    def __init__(self, message: str = "Invalid email or password"):
        self.message = message
        super().__init__(self.message)


class EmailAlreadyExistsError(Exception):
    """Raised when trying to register with an already-taken email."""

    def __init__(self, message: str = "Email already registered"):
        self.message = message
        super().__init__(self.message)


class ProviderError(Exception):
    """Raised when an OAuth provider fails."""

    def __init__(self, provider: str, message: str = "Provider error"):
        self.message = f"{provider}: {message}"
        super().__init__(self.message)
