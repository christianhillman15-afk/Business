"""AI reply drafts: review, edit, approve-and-post, reject.

Posting is human-in-the-loop and quota-enforced. The Session Executor /
connector publishes the approved text via the client's authorized account.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..connectors import connector_for
from ..crypto import decrypt
from ..database import get_db
from ..deps import get_current_user, record_audit
from ..models import (
    AgentResponse,
    ConnectedAccount,
    LeadMatch,
    LeadStatus,
    ResponseStatus,
    User,
)
from ..schemas import AgentResponseOut, DraftEditRequest
from ..services import remaining_quota

router = APIRouter(prefix="/api/responses", tags=["responses"])


def _load_owned_response(
    response_id: int, user: User, db: Session
) -> tuple[AgentResponse, LeadMatch]:
    resp = db.get(AgentResponse, response_id)
    if not resp:
        raise HTTPException(status_code=404, detail="Draft not found")
    lead = db.get(LeadMatch, resp.lead_id)
    if not lead or lead.user_id != user.id:
        raise HTTPException(status_code=404, detail="Draft not found")
    return resp, lead


@router.put("/{response_id}", response_model=AgentResponseOut)
def edit_draft(
    response_id: int,
    payload: DraftEditRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resp, _ = _load_owned_response(response_id, user, db)
    if resp.status == ResponseStatus.posted:
        raise HTTPException(status_code=409, detail="Already posted")
    resp.generated_text = payload.generated_text
    db.commit()
    db.refresh(resp)
    return resp


@router.post("/{response_id}/approve", response_model=AgentResponseOut)
def approve_and_post(
    response_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resp, lead = _load_owned_response(response_id, user, db)
    if resp.status == ResponseStatus.posted:
        raise HTTPException(status_code=409, detail="Already posted")

    if not user.automation_enabled:
        raise HTTPException(
            status_code=409, detail="Automation is turned off for this account"
        )
    if remaining_quota(db, user) <= 0:
        raise HTTPException(
            status_code=429, detail="Daily post quota exhausted. Try again tomorrow."
        )

    account = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.user_id == user.id,
            ConnectedAccount.provider == lead.provider,
        )
        .first()
    )
    credential = decrypt(account.encrypted_session) if account else None
    connector = connector_for(lead.provider.value, credential=credential)
    ok = connector.publish(post_url=lead.post_url, reply_text=resp.generated_text)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to publish reply")

    resp.status = ResponseStatus.posted
    resp.posted_at = datetime.now(timezone.utc)
    lead.status = LeadStatus.engaged
    db.commit()
    db.refresh(resp)
    record_audit(
        db,
        "response.post",
        user_id=user.id,
        detail=f"lead={lead.id} provider={lead.provider.value}",
        request=request,
    )
    return resp


@router.post("/{response_id}/reject", response_model=AgentResponseOut)
def reject_draft(
    response_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resp, lead = _load_owned_response(response_id, user, db)
    if resp.status == ResponseStatus.posted:
        raise HTTPException(status_code=409, detail="Already posted")
    resp.status = ResponseStatus.rejected
    lead.status = LeadStatus.dismissed
    db.commit()
    db.refresh(resp)
    return resp
