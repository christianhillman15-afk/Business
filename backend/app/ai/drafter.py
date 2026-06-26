"""Reply drafting: write a natural, human-sounding reply that merges the
client's services, price ranges, and phone number for a matched lead.
"""
from __future__ import annotations

from ..config import settings
from ..models import ClientPricingProfile, LeadMatch
from .client import get_ai

_SYSTEM = (
    "You write the reply a real local tradesperson would post when a neighbor "
    "asks for their service in a community group (Nextdoor/Facebook). Goal: be "
    "the helpful, trustworthy neighbor they call.\n"
    "Rules:\n"
    "- Warm, human, and specific — acknowledge what they actually asked for "
    "(their problem or job), don't be generic.\n"
    "- 2-3 short sentences. Plain language, no marketing fluff, no hashtags, no "
    "emoji spam, no ALL CAPS.\n"
    "- Naturally weave in the business name, the specific service, a price/range "
    "if provided, and the phone number with a clear nudge to call or text.\n"
    "- If it fits, mention availability (e.g. same-day/this week) to create a "
    "gentle reason to reach out now.\n"
    "- Sound like one honest message from a person, never like an ad or a bot."
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
        f"Hi! Sorry you're dealing with this — I run {business} and handle "
        f"{trade} right here in the area, often same week. "
        f"Typical pricing: {price_list}. "
        f"Call or text me at {phone} and I'll get you a quick quote and a time "
        f"that works."
    )
