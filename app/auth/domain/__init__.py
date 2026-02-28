"""Auth domain — value objects and exceptions."""

from enum import StrEnum


class OAuthProvider(StrEnum):
    GOOGLE = "google"
    APPLE = "apple"


class InvalidTokenError(Exception):
    """Raised when an OAuth token is invalid."""

    def __init__(self, message: str = "Invalid token"):
        self.message = message
        super().__init__(self.message)


class ProviderError(Exception):
    """Raised when an OAuth provider fails."""

    def __init__(self, provider: str, message: str = "Provider error"):
        self.message = f"{provider}: {message}"
        super().__init__(self.message)
