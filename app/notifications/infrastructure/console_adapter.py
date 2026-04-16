"""Notifications infrastructure — Console (stdout) email adapter for dev mode."""

import logging

logger = logging.getLogger("nutricia.notifications")


class ConsoleEmailAdapter:
    """Dev-mode email adapter: logs reset tokens to stdout instead of sending email."""

    async def send_reset_email(
        self,
        to: str,
        token: str,
        reset_url: str,
    ) -> None:
        """Log the reset token to stdout at INFO level."""
        logger.info("RESET_TOKEN for %s: %s", to, token)
        logger.info("Reset URL: %s", reset_url)
