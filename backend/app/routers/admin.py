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
    ConnectedAccount,
    ConnectionHealth,
    LeadMatch,
    OutreachRecruit,
    ResponseStatus,
    SubscriptionStatus,
    SupportTicket,
    TicketStatus,
    User,
    UserRole,
)
from datetime import datetime, timezone

from ..config import settings
from ..email import send_email
from ..notifications import notify
from ..schemas import (
    AdminUserOut,
    AuditLogOut,
    ConvertRecruitRequest,
    ManagedAccountOut,
    RecruitOut,
    TicketOut,
)
from ..security import create_magic_token
from ..services import create_trial_user, run_recruiting

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


@router.get("/provisioning", response_model=list[ManagedAccountOut])
def list_provisioning(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    """Managed Business Page setups awaiting the team to finish provisioning."""
    rows = db.execute(
        select(ConnectedAccount, User)
        .join(User, ConnectedAccount.user_id == User.id)
        .where(ConnectedAccount.health == ConnectionHealth.provisioning)
        .order_by(ConnectedAccount.connected_at.desc())
    ).all()
    return [
        ManagedAccountOut(
            id=acc.id,
            provider=acc.provider,
            auth_method=acc.auth_method,
            health=acc.health,
            business_name=u.business_name,
            email=u.email,
            connected_at=acc.connected_at,
        )
        for acc, u in rows
    ]


@router.post("/accounts/{account_id}/activate", response_model=ManagedAccountOut)
def activate_managed_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Mark a managed Business Page as live once the team has set it up."""
    acc = db.get(ConnectedAccount, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    acc.health = ConnectionHealth.healthy
    db.commit()
    db.refresh(acc)
    u = db.get(User, acc.user_id)
    if u:
        notify(
            db,
            u,
            kind="page_live",
            title=f"Your {acc.provider.value} Business Page is live",
            body="We've finished setting up your Business Page. The AI can now post for you.",
            email=True,
        )
    return ManagedAccountOut(
        id=acc.id,
        provider=acc.provider,
        auth_method=acc.auth_method,
        health=acc.health,
        business_name=u.business_name if u else None,
        email=u.email if u else "",
        connected_at=acc.connected_at,
    )


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


@router.post("/recruits/{recruit_id}/convert", response_model=RecruitOut)
def convert_recruit(
    recruit_id: int,
    payload: ConvertRecruitRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Convert a recruited prospect into a passwordless trial customer and email
    them a one-click sign-in link."""
    recruit = db.get(OutreachRecruit, recruit_id)
    if not recruit:
        raise HTTPException(status_code=404, detail="Recruit not found")

    user, created = create_trial_user(
        db,
        email=payload.email,
        business_name=payload.business_name or recruit.contact_name,
        phone=payload.phone,
        nextdoor_handle=payload.nextdoor_handle or recruit.nextdoor_handle,
        plan_code=payload.plan_code,
        source="recruit",
    )
    recruit.email = payload.email
    recruit.phone = payload.phone
    recruit.nextdoor_handle = payload.nextdoor_handle or recruit.nextdoor_handle
    recruit.converted_user_id = user.id
    recruit.trial_signup_at = recruit.trial_signup_at or datetime.now(timezone.utc)
    db.commit()
    db.refresh(recruit)

    link = f"{settings.frontend_base_url}/auth/magic?token={create_magic_token(user.id)}"
    send_email(
        user.email,
        "Your LeadPilot trial is ready",
        f"Welcome! Click to sign in (valid 30 minutes):\n{link}",
    )
    if created:
        notify(
            db,
            user,
            kind="welcome",
            title="Your LeadPilot trial is ready 🎉",
            body="We've emailed you a one-click sign-in link.",
        )
    return recruit


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
