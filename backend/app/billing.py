"""Billing abstraction.

Two providers behind one interface:
- **Mock** (default, no Stripe key): plan changes activate immediately.
- **Stripe**: creates a Checkout Session and activates on webhook confirmation.

Stripe is only used when ``STRIPE_SECRET_KEY`` is set; otherwise the mock keeps
the whole flow working in development.
"""
from __future__ import annotations

import logging

from .config import settings
from .plans import Plan

logger = logging.getLogger("leadpilot.billing")

try:  # pragma: no cover - import guard
    import stripe
except Exception:  # noqa: BLE001
    stripe = None  # type: ignore[assignment]


def stripe_enabled() -> bool:
    return bool(settings.stripe_secret_key) and stripe is not None


def _client():
    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_checkout(*, user_id: int, email: str, plan: Plan) -> str | None:
    """Return a Stripe Checkout URL, or None when using the mock provider."""
    if not stripe_enabled():
        return None

    price_id = settings.stripe_price_map.get(plan.code)
    try:
        client = _client()
        if price_id:
            line_items = [{"price": price_id, "quantity": 1}]
        else:
            # Fall back to an ad-hoc price so checkout works without pre-created
            # Stripe Price objects (use a real price_id in production).
            line_items = [
                {
                    "price_data": {
                        "currency": "usd",
                        "recurring": {"interval": "month"},
                        "unit_amount": plan.price_monthly * 100,
                        "product_data": {"name": f"LeadPilot {plan.name}"},
                    },
                    "quantity": 1,
                }
            ]
        session = client.checkout.Session.create(
            mode="subscription",
            line_items=line_items,
            customer_email=email,
            client_reference_id=str(user_id),
            metadata={"user_id": str(user_id), "plan_code": plan.code},
            success_url=f"{settings.frontend_base_url}/billing?status=success",
            cancel_url=f"{settings.frontend_base_url}/billing?status=cancel",
        )
        return session.url
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe checkout creation failed: %s", exc)
        return None


def parse_webhook(payload: bytes, signature: str | None) -> dict | None:
    """Validate and parse a Stripe webhook. Returns the event dict or None."""
    if not stripe_enabled():
        return None
    try:
        if settings.stripe_webhook_secret and signature:
            return _client().Webhook.construct_event(
                payload, signature, settings.stripe_webhook_secret
            )
        # No signing secret configured — parse without verification (dev only).
        import json

        return json.loads(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe webhook parse failed: %s", exc)
        return None
