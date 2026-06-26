"""Registration, login, and current-user endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, record_audit
from ..models import (
    ClientPricingProfile,
    Subscription,
    SubscriptionStatus,
    User,
    UserRole,
)
from ..config import settings
from ..email import send_email
from ..models import OutreachRecruit
from ..notifications import notify
from ..plans import DEFAULT_PLAN_CODE, get_plan
from ..schemas import (
    LoginRequest,
    MagicLinkRequest,
    MagicVerifyRequest,
    RegisterRequest,
    StartTrialRequest,
    TokenResponse,
    UserOut,
)
from ..security import (
    create_access_token,
    create_magic_token,
    hash_password,
    verify_magic_token,
    verify_password,
)
from ..services import create_trial_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    plan = get_plan(payload.plan_code) or get_plan(DEFAULT_PLAN_CODE)
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.provider,
        business_name=payload.business_name,
    )
    user.subscription = Subscription(
        plan_code=plan.code,
        status=SubscriptionStatus.trialing,
        trial_end=datetime.now(timezone.utc) + timedelta(days=7),
    )
    user.pricing_profile = ClientPricingProfile()
    db.add(user)
    db.commit()
    db.refresh(user)

    record_audit(
        db, "user.register", user_id=user.id, detail=user.email, request=request
    )
    notify(
        db,
        user,
        kind="welcome",
        title="Welcome to LeadPilot 🎉",
        body=(
            "Your 7-day trial is active. Next: connect an account and set your "
            "trade so the AI can start finding local leads for you."
        ),
        email=True,
    )
    token = create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    record_audit(db, "user.login", user_id=user.id, request=request)
    token = create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=token)


def _send_magic_link(user: User, *, new_account: bool) -> None:
    token = create_magic_token(user.id)
    link = f"{settings.frontend_base_url}/auth/magic?token={token}"
    subject = (
        "Welcome to LeadPilot — your sign-in link"
        if new_account
        else "Your LeadPilot sign-in link"
    )
    send_email(
        user.email,
        subject,
        f"Click to sign in (valid 30 minutes):\n{link}",
    )


@router.post("/start-trial", status_code=201)
def start_trial(
    payload: StartTrialRequest, request: Request, db: Session = Depends(get_db)
):
    """Profile-based, passwordless trial signup.

    This is the endpoint the onboarding flow (or the public trial page) calls
    once a prospect provides their email/phone — the person is now in the system
    keyed to their Nextdoor profile, and gets a one-click sign-in link by email.
    """
    user, created = create_trial_user(
        db,
        email=payload.email,
        business_name=payload.business_name,
        contact_name=payload.name,
        phone=payload.phone,
        nextdoor_handle=payload.nextdoor_handle,
        plan_code=payload.plan_code,
        source="recruit" if payload.recruit_id else "trial_page",
    )

    if payload.recruit_id:
        recruit = db.get(OutreachRecruit, payload.recruit_id)
        if recruit:
            recruit.email = payload.email
            recruit.phone = payload.phone
            recruit.nextdoor_handle = payload.nextdoor_handle
            recruit.converted_user_id = user.id
            recruit.trial_signup_at = recruit.trial_signup_at or datetime.now(
                timezone.utc
            )
            db.commit()

    if created:
        record_audit(
            db, "trial.start", user_id=user.id, detail=user.email, request=request
        )
        notify(
            db,
            user,
            kind="welcome",
            title="Your LeadPilot trial is ready 🎉",
            body="We've emailed you a one-click sign-in link to get started.",
        )
    _send_magic_link(user, new_account=created)
    return {"ok": True, "created": created}


@router.post("/magic/request")
def magic_request(payload: MagicLinkRequest, db: Session = Depends(get_db)):
    """Email a one-click sign-in link (passwordless login). Always 200 so we
    don't reveal whether an email is registered."""
    user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if user:
        _send_magic_link(user, new_account=False)
    return {"ok": True}


@router.post("/magic/verify", response_model=TokenResponse)
def magic_verify(payload: MagicVerifyRequest, db: Session = Depends(get_db)):
    user_id = verify_magic_token(payload.token)
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired link")
    return TokenResponse(access_token=create_access_token(str(user.id), user.role.value))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
