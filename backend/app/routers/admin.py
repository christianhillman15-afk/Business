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
    ClientContact,
    ClientPricingProfile,
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
import math
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..email import send_email
from ..notifications import notify
from ..schemas import (
    AdminUserOut,
    AuditLogOut,
    ClientContactIn,
    ClientDetail,
    ClientSummary,
    ClientUpdate,
    ConvertRecruitRequest,
    ManagedAccountOut,
    RecruitOut,
    TicketOut,
    TrialUpdate,
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


# --- Client CRM -------------------------------------------------------------
def _get_provider(db: Session, client_id: int) -> User:
    u = db.get(User, client_id)
    if not u or u.role != UserRole.provider:
        raise HTTPException(status_code=404, detail="Client not found")
    return u


def _services(user: User) -> list[str]:
    raw = user.pricing_profile.service_categories if user.pricing_profile else ""
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def _trial_info(user: User):
    sub = user.subscription
    active = bool(sub and sub.status == SubscriptionStatus.trialing)
    end = sub.trial_end if sub else None
    days = None
    if end is not None:
        e = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
        days = max(0, math.ceil((e - datetime.now(timezone.utc)).total_seconds() / 86400))
    return active, days, end


def _summary(user: User) -> ClientSummary:
    active, days, _ = _trial_info(user)
    return ClientSummary(
        id=user.id,
        business_name=user.business_name,
        contact_name=user.contact_name,
        city=user.city,
        state=user.state,
        client_status=user.client_status,
        claimed_by=user.claimed_by,
        plan_code=user.subscription.plan_code if user.subscription else None,
        trial_active=active,
        trial_days_left=days,
    )


def _detail(user: User) -> ClientDetail:
    active, days, end = _trial_info(user)
    return ClientDetail(
        id=user.id,
        email=user.email,
        business_name=user.business_name,
        contact_name=user.contact_name,
        phone=user.phone,
        city=user.city,
        state=user.state,
        service_radius_miles=user.service_radius_miles,
        client_notes=user.client_notes,
        bot_notes=user.bot_notes,
        claimed_by=user.claimed_by,
        client_status=user.client_status,
        trade=user.pricing_profile.trade if user.pricing_profile else None,
        services=_services(user),
        plan_code=user.subscription.plan_code if user.subscription else None,
        trial_active=active,
        trial_days_left=days,
        trial_end=end,
        contacts=[
            {"id": c.id, "name": c.name, "phone": c.phone, "email": c.email}
            for c in user.contacts
        ],
    )


@router.get("/clients", response_model=list[ClientSummary])
def list_clients(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    users = (
        db.execute(
            select(User)
            .where(User.role == UserRole.provider)
            .order_by(User.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_summary(u) for u in users]


@router.get("/clients/{client_id}", response_model=ClientDetail)
def get_client(
    client_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    return _detail(_get_provider(db, client_id))


@router.patch("/clients/{client_id}", response_model=ClientDetail)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = _get_provider(db, client_id)
    data = payload.model_dump(exclude_unset=True)
    services = data.pop("services", None)
    trade = data.pop("trade", None)
    for key, value in data.items():
        setattr(user, key, value)
    if trade is not None or services is not None:
        prof = user.pricing_profile
        if prof is None:
            prof = ClientPricingProfile(user_id=user.id)
            user.pricing_profile = prof
            db.add(prof)
        if trade is not None:
            prof.trade = trade
        if services is not None:
            prof.service_categories = ", ".join(services)
    db.commit()
    db.refresh(user)
    return _detail(user)


@router.patch("/clients/{client_id}/trial", response_model=ClientDetail)
def update_trial(
    client_id: int,
    payload: TrialUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = _get_provider(db, client_id)
    sub = user.subscription
    if sub is None:
        raise HTTPException(status_code=404, detail="Client has no subscription")
    if payload.days_left is not None:
        sub.trial_end = datetime.now(timezone.utc) + timedelta(
            days=max(0, payload.days_left)
        )
        sub.status = SubscriptionStatus.trialing
    if payload.trial_active is not None:
        sub.status = (
            SubscriptionStatus.trialing
            if payload.trial_active
            else SubscriptionStatus.active
        )
    db.commit()
    db.refresh(user)
    return _detail(user)


@router.post("/clients/{client_id}/contacts", response_model=ClientDetail)
def add_contact(
    client_id: int,
    payload: ClientContactIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = _get_provider(db, client_id)
    db.add(
        ClientContact(
            user_id=user.id,
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
        )
    )
    db.commit()
    db.refresh(user)
    return _detail(user)


@router.delete("/clients/{client_id}/contacts/{contact_id}", response_model=ClientDetail)
def delete_contact(
    client_id: int,
    contact_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = _get_provider(db, client_id)
    contact = db.get(ClientContact, contact_id)
    if contact and contact.user_id == user.id:
        db.delete(contact)
        db.commit()
        db.refresh(user)
    return _detail(user)
