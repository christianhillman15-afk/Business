"""Reply drafting: write a natural, human-sounding reply that merges the
client's services, price ranges, and phone number for a matched lead.
"""
from __future__ import annotations

from ..config import settings
from ..models import ClientPricingProfile, LeadMatch
from .client import get_ai

_SYSTEM = (
    "You write short, friendly, genuinely helpful replies on behalf of a local "
    "service business responding to someone asking for that service in a "
    "community group. Sound like a real local tradesperson, not an ad. Keep it "
    "to 2-3 sentences. Naturally include the service offered, a price range if "
    "provided, and the phone number. No hashtags, no emoji spam, no ALL CAPS."
)


def draft_reply(lead: LeadMatch, profile: ClientPricingProfile | None) -> str:
    trade = (profile.trade if profile else None) or "the work you need"
    price_list = (profile.price_list if profile else "") or "fair, upfront pricing"
    phone = (profile.phone if profile else None) or "(call for a quote)"
    business = lead.user.business_name or "a local pro"

    ai = get_ai()
    if ai.enabled:
        prompt = (
            f"Business name: {business}\n"
            f"Trade: {trade}\n"
            f"Pricing: {price_list}\n"
            f"Phone: {phone}\n\n"
            f"They posted:\n\"\"\"\n{lead.content}\n\"\"\"\n\n"
            "Write the reply."
        )
        text = ai.complete_text(
            system=_SYSTEM,
            prompt=prompt,
            model=settings.leadpilot_ai_model,
            max_tokens=400,
        )
        if text:
            return text

    return _fallback_reply(business, trade, price_list, phone)


def _fallback_reply(business: str, trade: str, price_list: str, phone: str) -> str:
    return (
        f"Hi! I run {business} and handle {trade} in the area. "
        f"Happy to help — typical pricing: {price_list}. "
        f"Give me a call or text at {phone} and I can get you a quick quote."
    )
