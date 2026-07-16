"""Pricing profile, automation toggle, and plan catalog."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..connectors import PROVIDER_CAPABILITIES
from ..database import get_db
from ..deps import get_current_user
from ..models import ClientPricingProfile, User
from ..plans import PLANS
from ..schemas import PlanOut, PricingProfileIn, PricingProfileOut

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/capabilities")
def capabilities():
    """Per-platform capabilities that drive the dashboard workflow."""
    return PROVIDER_CAPABILITIES


def _split(csv: str | None) -> list[str]:
    return [s.strip() for s in (csv or "").split(",") if s.strip()]


def _profile_out(p: ClientPricingProfile) -> PricingProfileOut:
    return PricingProfileOut(
        trade=p.trade,
        service_categories=_split(p.service_categories),
        price_list=p.price_list,
        phone=p.phone,
        target_neighborhoods=_split(p.target_neighborhoods),
    )


@router.get("/plans", response_model=list[PlanOut])
def list_plans():
    return [
        PlanOut(
            code=p.code,
            name=p.name,
            price_monthly=p.price_monthly,
            daily_post_quota=p.daily_post_quota,
        )
        for p in PLANS.values()
    ]


@router.get("/profile", response_model=PricingProfileOut)
def get_profile(user: User = Depends(get_current_user)):
    return _profile_out(user.pricing_profile)


@router.put("/profile", response_model=PricingProfileOut)
def update_profile(
    payload: PricingProfileIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = user.pricing_profile
    p.trade = payload.trade
    p.service_categories = ", ".join(payload.service_categories)
    p.price_list = payload.price_list
    p.phone = payload.phone
    p.target_neighborhoods = ", ".join(payload.target_neighborhoods)
    db.commit()
    db.refresh(p)
    return _profile_out(p)


@router.post("/automation/toggle")
def toggle_automation(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    user.automation_enabled = not user.automation_enabled
    db.commit()
    return {"automation_enabled": user.automation_enabled}
