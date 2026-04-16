"""Auth domain — repository ports."""

import uuid
from typing import Protocol

from app.auth.domain.entities import PasswordResetToken


class PasswordResetTokenRepository(Protocol):
    """Port for persisting and retrieving password reset tokens."""

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        """Persist a new reset token and return it."""
        ...

    async def find_by_token(self, token: str) -> PasswordResetToken | None:
        """Find a token record by its raw token string."""
        ...

    async def mark_used(self, token_id: uuid.UUID) -> None:
        """Mark a token as used so it cannot be reused."""
        ...
