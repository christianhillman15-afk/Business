"""Transactional email.

Default backend is ``console`` (emails are logged, so the app works with no mail
provider). Set ``EMAIL_BACKEND=smtp`` plus the SMTP_* settings (works with
Mailgun, SES, Postmark, etc.) to send real email.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from .config import settings

logger = logging.getLogger("leadpilot.email")


def send_email(to: str, subject: str, body: str) -> bool:
    if settings.email_backend != "smtp" or not settings.smtp_host:
        logger.info("[email:console] to=%s subject=%s\n%s", to, subject, body)
        return True

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            if settings.smtp_use_tls:
                s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("SMTP send failed (to=%s): %s", to, exc)
        return False
