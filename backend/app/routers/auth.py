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
from ..plans import DEFAULT_PLAN_CODE, get_plan
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..security import create_access_token, hash_password, verify_password

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


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
