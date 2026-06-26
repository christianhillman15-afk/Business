"""Two-way SMS: customers text their LeadPilot number and the assistant texts
back. This is the same assistant as the in-app chat, so a customer can run their
whole relationship with the bot from their phone.

Wire Twilio's inbound webhook (Messaging → "A message comes in") to
POST {OAUTH_REDIRECT_BASE}/api/sms/inbound. We reply with TwiML, so it works
even before outbound Twilio credentials are configured. See docs/SMS.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.support import answer, should_escalate
from ..database import get_db
from ..models import SupportMessage, SupportTicket, TicketStatus, User
from ..notifications import notify_admins
from ..sms import normalize_phone

router = APIRouter(prefix="/api/sms", tags=["sms"])


def _twiml(message: str) -> Response:
    body = (
        message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
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
            "plan?”, or “how do I connect Nextdoor?”"
        )

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
