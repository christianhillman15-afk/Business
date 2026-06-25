"""Support chatbot: answers onboarding and billing questions, and decides when
to escalate to a human admin.
"""
from __future__ import annotations

from ..config import settings
from ..plans import PLANS
from .client import get_ai

_ESCALATION_TRIGGERS = (
    "refund",
    "cancel",
    "human",
    "agent",
    "lawsuit",
    "legal",
    "complaint",
    "banned",
    "suspended",
    "charged twice",
    "speak to someone",
)


def _plans_blurb() -> str:
    return "; ".join(
        f"{p.name} ${p.price_monthly}/mo for {p.daily_post_quota} posts/day"
        for p in PLANS.values()
    )


_SYSTEM = (
    "You are LeadPilot's in-app support assistant for local service providers. "
    "Help them connect their Facebook/Nextdoor accounts, set up pricing, "
    "understand the daily post quota, and answer billing questions. Be concise "
    "and friendly. If you cannot resolve something (billing disputes, refunds, "
    "account suspensions, legal questions), tell them you're escalating to the "
    "team. Pricing tiers: " + _plans_blurb() + "."
)


def should_escalate(message: str) -> bool:
    text = message.lower()
    return any(trigger in text for trigger in _ESCALATION_TRIGGERS)


def answer(history: list[dict], message: str) -> str:
    ai = get_ai()
    if ai.enabled:
        transcript = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in history[-8:]
        )
        prompt = (
            (transcript + "\n" if transcript else "")
            + f"User: {message}\nAssistant:"
        )
        text = ai.complete_text(
            system=_SYSTEM,
            prompt=prompt,
            model=settings.leadpilot_ai_model,
            max_tokens=500,
        )
        if text:
            return text

    return _fallback_answer(message)


def _fallback_answer(message: str) -> str:
    text = message.lower()
    if "connect" in text or "facebook" in text or "nextdoor" in text:
        return (
            "To connect an account, open Onboarding → Connect accounts and follow "
            "the wizard. Facebook uses a secure login; Nextdoor links your "
            "neighborhood profile. Once connected you'll see a green health badge."
        )
    if "price" in text or "plan" in text or "cost" in text or "billing" in text:
        return (
            "Plans are billed monthly by your daily post quota: " + _plans_blurb()
            + ". You can change plans anytime under Billing."
        )
    if "quota" in text or "posts" in text:
        return (
            "Your plan sets how many AI-assisted posts you can approve per day. "
            "The counter resets at midnight in your local timezone. You'll get an "
            "alert when you're out of quota."
        )
    if should_escalate(message):
        return "I'm escalating this to a human on our team — they'll follow up by email shortly."
    return (
        "Happy to help! I can assist with connecting accounts, pricing/billing, "
        "and your daily quota. Could you tell me a bit more about what you need?"
    )
