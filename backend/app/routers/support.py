"""In-app AI support chatbot with human escalation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.support import answer, should_escalate
from ..database import get_db
from ..deps import get_current_user
from ..models import SupportMessage, SupportTicket, TicketStatus, User
from ..notifications import notify_admins
from ..schemas import SupportChatRequest, SupportChatResponse, TicketOut

router = APIRouter(prefix="/api/support", tags=["support"])


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.user_id == user.id)
        .order_by(SupportTicket.created_at.desc())
    )
    return db.execute(stmt).scalars().all()


@router.post("/chat", response_model=SupportChatResponse)
def chat(
    payload: SupportChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.ticket_id:
        ticket = db.get(SupportTicket, payload.ticket_id)
        if not ticket or ticket.user_id != user.id:
            raise HTTPException(status_code=404, detail="Ticket not found")
    else:
        ticket = SupportTicket(user_id=user.id, status=TicketStatus.open)
        db.add(ticket)
        db.flush()

    history = [{"role": m.role, "content": m.content} for m in ticket.messages]
    db.add(SupportMessage(ticket_id=ticket.id, role="user", content=payload.message))

    reply = answer(history, payload.message)
    escalate = should_escalate(payload.message)
    if escalate:
        ticket.escalated = True

    db.add(SupportMessage(ticket_id=ticket.id, role="assistant", content=reply))
    db.commit()

    if escalate:
        notify_admins(
            db,
            kind="support_escalation",
            title=f"Support escalation from {user.business_name or user.email}",
            body=f"Ticket #{ticket.id}: “{payload.message[:140]}”",
        )

    return SupportChatResponse(ticket_id=ticket.id, reply=reply, escalated=escalate)
