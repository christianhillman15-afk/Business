"""Connected social accounts (connection wizard)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, record_audit
from ..models import ConnectedAccount, ConnectionHealth, User
from ..schemas import ConnectAccountRequest, ConnectedAccountOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _obfuscate(credential: str | None) -> str | None:
    """The stub does not store real sessions; it keeps an opaque marker only.

    A real connector must AES-256-encrypt the captured session (see
    docs/COMPLIANCE.md and the spec's security requirements).
    """
    if not credential:
        return None
    return "stub-session:" + str(abs(hash(credential)) % 10_000_000)


@router.get("", response_model=list[ConnectedAccountOut])
def list_accounts(user: User = Depends(get_current_user)):
    return user.connected_accounts


@router.post("", response_model=ConnectedAccountOut, status_code=201)
def connect_account(
    payload: ConnectAccountRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user.id,
            ConnectedAccount.provider == payload.provider,
        )
    ).scalar_one_or_none()
    if existing:
        existing.display_name = payload.display_name or existing.display_name
        existing.encrypted_session = _obfuscate(payload.credential)
        existing.health = ConnectionHealth.healthy
        db.commit()
        db.refresh(existing)
        return existing

    account = ConnectedAccount(
        user_id=user.id,
        provider=payload.provider,
        display_name=payload.display_name,
        encrypted_session=_obfuscate(payload.credential),
        health=ConnectionHealth.healthy,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    record_audit(
        db,
        "account.connect",
        user_id=user.id,
        detail=payload.provider.value,
        request=request,
    )
    return account


@router.delete("/{account_id}", status_code=204)
def disconnect_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.get(ConnectedAccount, account_id)
    if not account or account.user_id != user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
