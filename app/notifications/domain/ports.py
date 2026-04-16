"""Notifications domain — EmailPort protocol."""

from typing import Protocol


class EmailPort(Protocol):
    """Port for sending transactional emails."""

    async def send_reset_email(
        self,
        to: str,
        token: str,
        reset_url: str,
    ) -> None:
        """Send a password reset email.

        Args:
            to: Recipient email address.
            token: Raw reset token (embedded in reset_url).
            reset_url: Full deep-link URL for the frontend reset screen.
        """
        ...
