"""Notifications infrastructure — SMTP email adapter for production."""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("nutricia.notifications")


class SmtpEmailAdapter:
    """Production SMTP email adapter using settings.SMTP_* config."""

    async def send_reset_email(
        self,
        to: str,
        token: str,
        reset_url: str,
    ) -> None:
        """Send a password reset email via SMTP."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Restablecer tu contraseña — NutricIA"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = (
            f"Hola,\n\n"
            f"Recibimos una solicitud para restablecer tu contraseña.\n\n"
            f"Hacé clic en el siguiente enlace (válido por 15 minutos):\n"
            f"{reset_url}\n\n"
            f"Si no solicitaste esto, ignorá este mensaje.\n\n"
            f"— Equipo NutricIA"
        )
        html_body = (
            f"<p>Hola,</p>"
            f"<p>Recibimos una solicitud para restablecer tu contraseña.</p>"
            f'<p><a href="{reset_url}">Restablecer contraseña</a> (válido 15 minutos)</p>'
            f"<p>Si no solicitaste esto, ignorá este mensaje.</p>"
            f"<p>— Equipo NutricIA</p>"
        )

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.smtp_from, to, msg.as_string())
                logger.info("Reset email sent to %s", to)
        except Exception as exc:
            logger.error("Failed to send reset email to %s: %s", to, exc)
            raise
