"""Custom Response Generator.

The client found a post themselves and wants a reply. We already know their
trade, services, pricing, and phone, so we generate an on-brand reply on demand.
Free trials are capped to a few per day; paid plans are unlimited.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.drafter import generate_reply
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import CustomResponse, User
from ..schemas import (
    GenerateRequest,
    GenerateResponse,
    GenerationOut,
    GenerationUsage,
)
from ..services import _local_midnight_utc, on_trial, subscription_active

router = APIRouter(prefix="/api/generate", tags=["generate"])


def _used_today(db: Session, user: User) -> int:
    start = _local_midnight_utc(user.timezone)
    return int(
        db.execute(
            select(func.count(CustomResponse.id)).where(
                CustomResponse.user_id == user.id,
                CustomResponse.created_at >= start,
            )
        ).scalar_one()
    )


def _usage(db: Session, user: User) -> GenerationUsage:
    used = _used_today(db, user)
    # Inactive (expired trial / canceled / no plan): no generations until they
    # pick a plan. Report honestly so the UI shows the upgrade prompt, not
    # "unlimited".
    if not subscription_active(user):
        return GenerationUsage(
            used_today=used,
            daily_limit=0,
            remaining=0,
            unlimited=False,
            on_trial=on_trial(user),
        )
    if on_trial(user):
        limit = settings.trial_generation_quota
        return GenerationUsage(
            used_today=used,
            daily_limit=limit,
            remaining=max(0, limit - used),
            unlimited=False,
            on_trial=True,
        )
    return GenerationUsage(
        used_today=used,
        daily_limit=None,
        remaining=None,
        unlimited=True,
        on_trial=False,
    )


@router.get("/usage", response_model=GenerationUsage)
def usage(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return _usage(db, user)


@router.get("/history", response_model=list[GenerationOut])
def history(
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            select(CustomResponse)
            .where(CustomResponse.user_id == user.id)
            .order_by(CustomResponse.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return rows


@router.post("", response_model=GenerateResponse)
def generate(
    payload: GenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not subscription_active(user):
        raise HTTPException(
            status_code=402,
            detail="Your trial has ended — choose a plan to keep generating replies.",
        )
    current = _usage(db, user)
    if not current.unlimited and (current.remaining or 0) <= 0:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You've used your {current.daily_limit} free trial generations "
                "today. Upgrade for unlimited."
            ),
        )

    reply = generate_reply(
        payload.post_content,
        user.pricing_profile,
        business_name=user.business_name,
        platform=payload.platform,
    )
    row = CustomResponse(
        user_id=user.id,
        post_content=payload.post_content[:4000],
        platform=payload.platform,
        reply=reply,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return GenerateResponse(id=row.id, reply=reply, usage=_usage(db, user))
