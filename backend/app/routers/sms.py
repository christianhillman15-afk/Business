"""Two-way SMS: customers text their LeadPilot number and the assistant texts
back. This is the same assistant as the in-app chat, so a customer can run their
whole relationship with the bot from their phone — get leads, ask questions, and
use quick text commands (STATUS, LEADS, HELP, STOP/START).

Wire Twilio's inbound webhook (Messaging → "A message comes in") to
POST {OAUTH_REDIRECT_BASE}/api/sms/inbound. We reply with TwiML, so it works
even before outbound Twilio credentials are configured. See docs/SMS.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.support import answer, should_escalate
from ..config import settings
from ..database import get_db
from ..models import (
    LeadMatch,
    LeadStatus,
    SupportMessage,
    SupportTicket,
    TicketStatus,
    User,
)
from ..notifications import notify_admins
from ..services import daily_quota, on_trial, posts_used_today, remaining_quota
from ..sms import normalize_phone

router = APIRouter(prefix="/api/sms", tags=["sms"])

# Standard carrier opt-out / opt-in / help keywords (matched on the whole text).
_STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
_START_WORDS = {"START", "UNSTOP", "YES"}
_HELP_WORDS = {"HELP", "INFO"}


def _twiml(message: str) -> Response:
    body = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{body}</Message></Response>'
    return Response(content=xml, media_type="application/xml")


def _find_user_by_phone(db: Session, from_number: str) -> User | None:
    target = normalize_phone(from_number)
    if not target:
        return None
    # Phones are stored as free text; match on the last 10 digits in Python.
    users = db.execute(select(User).where(User.phone.is_not(None))).scalars().all()
    for u in users:
        if normalize_phone(u.phone) == target:
            return u
    return None


def _handle_command(db: Session, user: User, message: str) -> str | None:
    """Return a reply for a recognized text command, or None to fall through to
    the conversational AI. Commands are matched on the whole message so phrases
    like 'cancel my plan' still reach the assistant (and escalate)."""
    norm = message.strip().upper()

    if norm in _STOP_WORDS:
        user.sms_enabled = False
        return (
            "You're unsubscribed from LeadPilot texts. Reply START anytime to "
            "turn them back on."
        )
    if norm in _START_WORDS:
        user.sms_enabled = True
        return (
            "You're back on ✅ I'll text you new leads and updates. Reply HELP "
            "for options."
        )
    if norm in _HELP_WORDS:
        return (
            "LeadPilot texts you new leads (the post link + a ready-to-send "
            "reply) and answers questions. Reply STATUS for your plan, LEADS for "
            "what's waiting, or just ask me anything. Reply STOP to opt out."
        )
    if norm == "STATUS":
        q = daily_quota(user)
        used = posts_used_today(db, user)
        rem = remaining_quota(db, user)
        plan = (
            "Free trial"
            if on_trial(user)
            else (user.subscription.plan_code.title() if user.subscription else "—")
        )
        return (
            f"Plan: {plan} — up to {q} replies/day. {used} posted today, "
            f"{rem} left. Reply LEADS to see what's waiting."
        )
    if norm in {"LEADS", "LEAD"}:
        waiting = db.execute(
            select(func.count(LeadMatch.id)).where(
                LeadMatch.user_id == user.id,
                LeadMatch.status == LeadStatus.drafted,
            )
        ).scalar_one()
        s = "" if waiting == 1 else "s"
        return (
            f"You have {waiting} lead{s} ready to review. "
            f"Open your dashboard: {settings.frontend_base_url}/dashboard"
        )
    return None


@router.post("/inbound")
def inbound_sms(
    db: Session = Depends(get_db),
    From: str = Form(default=""),
    Body: str = Form(default=""),
):
    """Twilio inbound message webhook. Replies with the assistant's answer."""
    message = (Body or "").strip()
    user = _find_user_by_phone(db, From)

    if user is None:
        return _twiml(
            "Hi! This number isn't linked to a LeadPilot account yet. Add this "
            "phone under Settings in your LeadPilot dashboard and text us again."
        )

    if not message:
        return _twiml(
            "Hi! Text me any question — like “how many leads today?”, “what's my "
            "plan?”, or “how do I connect Nextdoor?” Reply HELP for options."
        )

    # Quick text commands (opt-out/opt-in/help/status/leads) before the AI.
    command_reply = _handle_command(db, user, message)
    if command_reply is not None:
        db.commit()
        return _twiml(command_reply)

    # Reuse the user's open ticket as the running SMS conversation, or start one.
    ticket = db.execute(
        select(SupportTicket)
        .where(
            SupportTicket.user_id == user.id,
            SupportTicket.status == TicketStatus.open,
        )
        .order_by(SupportTicket.created_at.desc())
    ).scalars().first()
    if ticket is None:
        ticket = SupportTicket(user_id=user.id, status=TicketStatus.open)
        db.add(ticket)
        db.flush()

    history = [{"role": m.role, "content": m.content} for m in ticket.messages]
    db.add(SupportMessage(ticket_id=ticket.id, role="user", content=message))

    reply = answer(history, message)
    escalate = should_escalate(message)
    if escalate:
        ticket.escalated = True

    db.add(SupportMessage(ticket_id=ticket.id, role="assistant", content=reply))
    db.commit()

    if escalate:
        notify_admins(
            db,
            kind="support_escalation",
            title=f"SMS escalation from {user.business_name or user.email}",
            body=f"Ticket #{ticket.id}: “{message[:140]}”",
        )

    return _twiml(reply)
