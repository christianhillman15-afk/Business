"""Compose a proactive 'Business Post' for a client to broadcast to neighbors.

On Nextdoor this is the compliant, automatable way for the AI to post — a new
Business Post via the official Create Post API (there is no reply API). On
Facebook it maps to a Page post.
"""
from __future__ import annotations

from ..config import settings
from ..models import ClientPricingProfile
from .client import get_ai

_SYSTEM = (
    "You write a short, neighborly Business Post for a local service provider to "
    "share with nearby neighbors on a community platform (like Nextdoor). 1-3 "
    "sentences, warm and local, no hard-sell or hype. Mention the service, a "
    "price hook if provided, the service area, and the phone number. No "
    "hashtags, no emoji spam, no ALL CAPS."
)


def compose_business_post(
    business_name: str, profile: ClientPricingProfile | None, *, topic: str | None = None
) -> str:
    trade = (profile.trade if profile else None) or "local services"
    price = (profile.price_list if profile else "") or "fair, upfront pricing"
    phone = (profile.phone if profile else None) or "(call for a quote)"
    area = (profile.target_neighborhoods if profile else "") or "the neighborhood"

    ai = get_ai()
    if ai.enabled:
        prompt = (
            f"Business: {business_name}\nTrade: {trade}\nPricing: {price}\n"
            f"Service area: {area}\nPhone: {phone}\n"
            + (f"Theme/offer to feature: {topic}\n" if topic else "")
            + "\nWrite the Business Post."
        )
        text = ai.complete_text(
            system=_SYSTEM,
            prompt=prompt,
            model=settings.leadpilot_ai_model,
            max_tokens=300,
        )
        if text:
            return text

    return (
        f"Hi neighbors! {business_name} here — your local {trade} serving {area}. "
        f"{price}. Need a hand? Call or text {phone} and we'll take care of it."
    )
