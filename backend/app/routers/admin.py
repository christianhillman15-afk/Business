"""Admin control panel: clients, tickets, recruiting log, audit trail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import (
    AgentResponse,
    AuditLog,
    LeadMatch,
    OutreachRecruit,
    ResponseStatus,
    SupportTicket,
    TicketStatus,
    User,
    UserRole,
)
from ..models import SubscriptionStatus
from ..schemas import AdminUserOut, AuditLogOut, RecruitOut, TicketOut
from ..services import run_recruiting

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    def count(model, *where):
        return int(db.execute(select(func.count(model.id)).where(*where)).scalar_one())

    return {
        "providers": count(User, User.role == UserRole.provider),
        "leads": count(LeadMatch),
        "posted_replies": count(
            AgentResponse, AgentResponse.status == ResponseStatus.posted
        ),
        "open_tickets": count(SupportTicket, SupportTicket.status == TicketStatus.open),
        "escalated_tickets": count(SupportTicket, SupportTicket.escalated.is_(True)),
        "recruits_contacted": count(
            OutreachRecruit, OutreachRecruit.message_sent.is_(True)
        ),
    }


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    stmt = select(User).order_by(User.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    escalated_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc())
    if escalated_only:
        stmt = stmt.where(SupportTicket.escalated.is_(True))
    return db.execute(stmt).scalars().all()


@router.post("/tickets/{ticket_id}/resolve", response_model=TicketOut)
def resolve_ticket(
    ticket_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = TicketStatus.resolved
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/audit", response_model=list[AuditLogOut])
def audit_log(
    limit: int = 100, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/recruits", response_model=list[RecruitOut])
def list_recruits(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    stmt = select(OutreachRecruit).order_by(OutreachRecruit.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.post("/recruiting/run", response_model=list[RecruitOut])
def run_recruiting_pipeline(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    return run_recruiting(db)


@router.post("/discovery/run-all")
def run_discovery_all(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    """Run a discovery sweep for every active provider with automation on."""
    from ..services import run_discovery

    providers = (
        db.execute(
            select(User).where(
                User.role == UserRole.provider, User.automation_enabled.is_(True)
            )
        )
        .scalars()
        .all()
    )
    total = 0
    for p in providers:
        if p.subscription and p.subscription.status in (
            SubscriptionStatus.active,
            SubscriptionStatus.trialing,
        ):
            total += len(run_discovery(db, p))
    return {"providers_scanned": len(providers), "leads_created": total}
