"""Account settings: update profile, set/change password, delete account."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, record_audit
from ..models import User
from ..schemas import AccountUpdateRequest, PasswordSetRequest, UserOut
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api/account", tags=["account"])


@router.patch("", response_model=UserOut)
def update_account(
    payload: AccountUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.business_name is not None:
        user.business_name = payload.business_name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.timezone is not None:
        user.timezone = payload.timezone
    if payload.nextdoor_handle is not None:
        user.nextdoor_handle = payload.nextdoor_handle
    if payload.sms_enabled is not None:
        user.sms_enabled = payload.sms_enabled
    db.commit()
    db.refresh(user)
    return user


@router.post("/password")
def set_password(
    payload: PasswordSetRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or change the password. If one already exists, the current password
    is required; passwordless (magic-link) accounts can set one freely."""
    if user.password_hash and not (
        payload.current_password
        and verify_password(payload.current_password, user.password_hash)
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    record_audit(db, "account.password_change", user_id=user.id, request=request)
    return {"ok": True}


@router.delete("", status_code=204)
def delete_account(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record_audit(db, "account.delete", user_id=user.id, detail=user.email, request=request)
    db.delete(user)  # cascades to subscription, profile, accounts, leads, tickets
    db.commit()
