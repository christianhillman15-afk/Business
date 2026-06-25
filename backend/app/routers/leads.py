"""Lead discovery and listing."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_active_user
from ..models import LeadMatch, LeadStatus, User
from ..schemas import LeadOut, QuotaOut
from ..services import daily_quota, on_trial, posts_used_today, run_discovery

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("", response_model=list[LeadOut])
def list_leads(
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(LeadMatch).where(LeadMatch.user_id == user.id)
    if status_filter:
        try:
            stmt = stmt.where(LeadMatch.status == LeadStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
    stmt = stmt.order_by(LeadMatch.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.post("/discover", response_model=list[LeadOut])
def discover(
    user: User = Depends(require_active_user), db: Session = Depends(get_db)
):
    """Run a discovery sweep: find posts, field-match them, draft replies."""
    return run_discovery(db, user)


@router.get("/quota", response_model=QuotaOut)
def quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    used = posts_used_today(db, user)
    limit = daily_quota(user)
    return QuotaOut(
        plan_code=user.subscription.plan_code if user.subscription else "growth",
        daily_quota=limit,
        used_today=used,
        remaining_today=max(0, limit - used),
        on_trial=on_trial(user),
    )


@router.post("/{lead_id}/dismiss", response_model=LeadOut)
def dismiss_lead(
    lead_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = db.get(LeadMatch, lead_id)
    if not lead or lead.user_id != user.id:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.status = LeadStatus.dismissed
    db.commit()
    db.refresh(lead)
    return lead
