"""Trial Recruiter AI.

Generates personalized messages pitching a 7-day free trial to other local
service providers discovered on social platforms.

Compliance note: real outbound recruiting must be opt-in and comply with
CAN-SPAM / TCPA / platform messaging policies (see docs/COMPLIANCE.md). This
module generates the message copy; whether and how it is delivered is gated by
``LEADPILOT_LIVE_CONNECTORS`` and your own consent controls.
"""
from __future__ import annotations

from ..config import settings
from .client import get_ai

_SYSTEM = (
    "You write short, warm, non-spammy outreach messages inviting a local "
    "service provider to try LeadPilot — a tool that finds them local jobs and "
    "drafts replies for approval. 2-3 sentences, friendly, no hype, mention the "
    "7-day free trial and that there's no upfront payment. Include a clear, "
    "honest opt-out note."
)


def generate_pitch(*, name: str | None, trade: str | None) -> str:
    who = name or "there"
    work = trade or "local services"
    ai = get_ai()
    if ai.enabled:
        prompt = (
            f"Recipient name: {who}\nTheir trade: {work}\n\n"
            "Write the trial invitation."
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
        f"Hi {who} — I run LeadPilot, which finds local {work} jobs and drafts "
        "replies for you to approve before anything posts. Want to try it free "
        "for 7 days, no card required? Reply STOP and I won't message again."
    )
