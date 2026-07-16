"""Subscription management.

Uses a built-in mock billing provider when STRIPE_SECRET_KEY is unset, so plan
selection works end-to-end in development. Wire real Stripe checkout where noted.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..billing import create_checkout, parse_webhook, stripe_enabled
from ..database import get_db
from ..deps import get_current_user, record_audit
from ..models import Subscription, SubscriptionStatus, User
from ..notifications import notify
from ..plans import get_plan
from ..schemas import SelectPlanRequest, SelectPlanResponse, SubscriptionOut

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionOut)
def get_subscription(user: User = Depends(get_current_user)):
    return user.subscription


@router.post("/select", response_model=SelectPlanResponse)
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
    checkout_url: str | None = None

    if stripe_enabled():
        # Real Stripe: create Checkout; activation happens on webhook.
        checkout_url = create_checkout(user_id=user.id, email=user.email, plan=plan)
        sub.external_ref = "stripe:pending"
    else:
        # Mock provider: activate immediately.
        sub.status = SubscriptionStatus.active
        sub.external_ref = f"mock:{plan.code}"

    db.commit()
    db.refresh(sub)
    record_audit(
        db, "subscription.select", user_id=user.id, detail=plan.code, request=request
    )
    if sub.status == SubscriptionStatus.active:
        notify(
            db,
            user,
            kind="billing",
            title=f"You're on the {plan.name} plan",
            body=f"${plan.price_monthly}/mo · {plan.daily_post_quota} AI posts per day.",
            email=True,
        )
    return SelectPlanResponse(subscription=sub, checkout_url=checkout_url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook: activate a subscription on checkout completion."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    event = parse_webhook(payload, sig)
    if not event:
        raise HTTPException(status_code=400, detail="Invalid webhook")

    if event.get("type") == "checkout.session.completed":
        obj = event["data"]["object"]
        meta = obj.get("metadata") or {}
        user_id = meta.get("user_id") or obj.get("client_reference_id")
        plan_code = meta.get("plan_code")
        if user_id:
            sub = (
                db.query(Subscription)
                .filter(Subscription.user_id == int(user_id))
                .first()
            )
            if sub:
                if plan_code:
                    sub.plan_code = plan_code
                sub.status = SubscriptionStatus.active
                sub.external_ref = obj.get("subscription") or "stripe:active"
                db.commit()
    return {"received": True}


@router.post("/cancel", response_model=SubscriptionOut)
def cancel(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    sub = user.subscription
    sub.status = SubscriptionStatus.canceled
    db.commit()
    db.refresh(sub)
    return sub
