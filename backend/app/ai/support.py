"""Support assistant: powers both the in-app chat and the two-way SMS bot.

Answers questions about how LeadPilot works using a shared knowledge base,
keeps a warm, plain-language tone for busy tradespeople, and decides when to
escalate to a human.
"""
from __future__ import annotations

from ..config import settings
from .client import get_ai
from .knowledge import SUGGESTED_QUESTIONS, knowledge_base, plans_blurb

_ESCALATION_TRIGGERS = (
    "refund",
    "cancel my",
    "double charge",
    "charged twice",
    "speak to someone",
    "talk to a person",
    "human",
    "lawsuit",
    "legal",
    "complaint",
    "banned",
    "suspended",
)

_SYSTEM = (
    "You are the LeadPilot assistant — a warm, upbeat, plain-spoken helper for "
    "local service business owners (plumbers, cleaners, landscapers, etc.). Most "
    "are not tech-savvy and many of them reach you by text message, so keep "
    "answers short, friendly, and concrete. Use everyday language, avoid jargon, "
    "and when it helps, point them to the exact place to tap (Setup, Dashboard, "
    "Billing, Settings). Never invent features. If they ask for a refund, dispute "
    "a charge, or want a human, reassure them you're looping in a teammate. "
    "Only answer using the product facts below.\n\n" + knowledge_base()
)


def suggested_questions() -> list[str]:
    """One-tap starter questions for the chat UI and SMS quick-replies."""
    return list(SUGGESTED_QUESTIONS)


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


# Deterministic, knowledgeable offline answers (used when no AI key is set, and
# the basis for the tests). Ordered most-specific first.
def _fallback_answer(message: str) -> str:
    t = message.lower()

    def has(*words: str) -> bool:
        return any(w in t for w in words)

    if has("text", "sms", "message") and has("bot", "you", "talk", "ask", "question"):
        return (
            "You can text me anytime at your LeadPilot number — ask things like "
            "“what's my plan?”, “how many leads today?”, or “how do I connect "
            "Facebook?” and I'll text right back. It's the same assistant as this "
            "chat, just over SMS, so you never have to log in."
        )
    if has("text", "sms") or (has("lead", "post") and has("notify", "alert", "send")):
        return (
            "Every time the bot finds a job in your trade, it texts you two "
            "messages: one with the post and its link, and a second with the "
            "suggested reply by itself so you can copy-paste it in one tap. Keep "
            "“Text me new leads” on in Settings and make sure your phone number "
            "is right."
        )
    if has("find", "how does", "how do you", "discover", "work"):
        return (
            "I watch local Nextdoor and Facebook groups for neighbors asking for "
            "the kind of work you do, then write a ready-to-send reply with your "
            "services, pricing, and phone number. You approve it before anything "
            "posts — and I text every lead straight to you. Set your trade under "
            "Setup, then tap “Scan for leads.”"
        )
    if has("connect", "facebook", "nextdoor", "account", "link my"):
        return (
            "Head to Setup → Connect accounts. Use the official “Connect” button "
            "(no password is ever shared with us) or pick “Set up a Business Page "
            "for me.” A green badge means you're connected. On Nextdoor I draft "
            "replies for you to post in one tap; on Facebook I can post for you "
            "automatically."
        )
    if has("price", "plan", "cost", "pricing", "how much", "billing"):
        return (
            "Plans are billed monthly by your daily reply limit (an “up to” cap): "
            + plans_blurb()
            + ". Every plan starts with a 7-day free trial — 1 reply/day, no card. "
            "Change plans anytime under Billing."
        )
    if has("quota", "limit", "how many", "per day", "daily"):
        return (
            "Your plan sets how many AI replies can post per day — it's an “up to” "
            "cap, since some days have fewer in-field leads. It resets at midnight "
            "in your local timezone, and I'll alert you when you're out."
        )
    if has("edit", "change the reply", "approve", "decline", "don't post"):
        return (
            "You're always in control. On each lead you can tap Edit to tweak the "
            "wording, Approve & post (or “I posted it” for Nextdoor), or Decline. "
            "Nothing goes out without your okay."
        )
    if has("not getting", "no leads", "why am i not", "isn't working", "not working"):
        return (
            "Let's get you leads. Check that (1) your Trade and Service categories "
            "are filled in under Setup, (2) your target neighborhoods are set, (3) "
            "an account is connected, and (4) you still have quota today. Then tap "
            "“Scan for leads.” Want me to walk through any of these?"
        )
    if has("trial", "free"):
        return (
            "The free trial runs 7 days with 1 AI reply per day — no card needed. "
            "Sign-in is a one-click email link, so there's no password to remember. "
            "You can pick a paid plan whenever you're ready."
        )
    if should_escalate(message):
        return (
            "I've noted this and I'm looping in a teammate who can help — they'll "
            "follow up by email shortly. Anything else I can do in the meantime?"
        )
    return (
        "Happy to help! I can explain how leads work, getting leads by text, "
        "pricing, connecting Nextdoor or Facebook, your daily limit, or billing. "
        "What would you like to know?"
    )
