"""Auth domain — entities."""

import uuid
from datetime import datetime


class PasswordResetToken:
    """Domain entity representing a password reset token."""

    def __init__(
        self,
        id: uuid.UUID,
        user_id: uuid.UUID,
        token: str,
        expires_at: datetime,
        used: bool = False,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.token = token
        self.expires_at = expires_at
        self.used = used
        self.created_at = created_at

    def is_expired(self, now: datetime) -> bool:
        """Return True if this token has passed its expiry time."""
        return now >= self.expires_at

    def is_valid(self, now: datetime) -> bool:
        """Return True if token can still be used (not used, not expired)."""
        return not self.used and not self.is_expired(now)
