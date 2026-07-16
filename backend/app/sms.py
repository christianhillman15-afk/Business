"""SMS notifications (lead alerts).

Default backend is ``console`` (messages are logged, so the app works with no
SMS provider). Set ``SMS_BACKEND=twilio`` plus the Twilio settings to send real
texts. Uses Twilio's REST API directly via httpx — no extra dependency.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger("leadpilot.sms")


def normalize_phone(phone: str | None) -> str:
    """Reduce a phone number to comparable digits (last 10, ignoring +1/format)."""
    if not phone:
        return ""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def sms_configured() -> bool:
    return settings.sms_backend == "twilio" and bool(
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_from_number
    )


def send_sms(to: str | None, body: str) -> bool:
    if not to:
        return False
    if not sms_configured():
        logger.info("[sms:console] to=%s\n%s", to, body)
        return True
    sid = settings.twilio_account_sid
    try:
        resp = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"From": settings.twilio_from_number, "To": to, "Body": body},
            auth=(sid, settings.twilio_auth_token or ""),
            timeout=15.0,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("SMS send failed (to=%s): %s", to, exc)
        return False
