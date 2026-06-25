"""Subscription management.

Uses a built-in mock billing provider when STRIPE_SECRET_KEY is unset, so plan
selection works end-to-end in development. Wire real Stripe checkout where noted.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, record_audit
from ..models import SubscriptionStatus, User
from ..plans import get_plan
from ..schemas import SelectPlanRequest, SubscriptionOut

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionOut)
def get_subscription(user: User = Depends(get_current_user)):
    return user.subscription


@router.post("/select", response_model=SubscriptionOut)
def select_plan(
    payload: SelectPlanRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = get_plan(payload.plan_code)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")

    sub = user.subscription
    sub.plan_code = plan.code
    # With a real Stripe key, create a Checkout session here and only flip to
    # active on webhook confirmation. The mock provider activates immediately.
    if settings.stripe_secret_key:
        sub.external_ref = "stripe:pending"
    else:
        sub.status = SubscriptionStatus.active
        sub.external_ref = f"mock:{plan.code}"
    db.commit()
    db.refresh(sub)
    record_audit(
        db, "subscription.select", user_id=user.id, detail=plan.code, request=request
    )
    return sub


@router.post("/cancel", response_model=SubscriptionOut)
def cancel(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    sub = user.subscription
    sub.status = SubscriptionStatus.canceled
    db.commit()
    db.refresh(sub)
    return sub
