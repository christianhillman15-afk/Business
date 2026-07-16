"""Connected social accounts (connection wizard).

Three connection methods, none of which require a client to hand over a password:

- ``oauth`` — the client authorizes us through the platform's official flow; we
  store the returned token (encrypted), never a password. Recommended.
- ``managed_business_page`` — for clients who don't want to connect anything
  personal: LeadPilot provisions and operates a dedicated Business Page for the
  business. No credentials are involved; the account starts in ``provisioning``
  until the team finishes setup.
- ``session`` — advanced/discouraged: a captured session token, encrypted at rest.

We never fabricate fake personal/neighbor accounts — that violates platform
terms and gets accounts banned (see docs/COMPLIANCE.md).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crypto import encrypt
from ..database import get_db
from ..deps import get_current_user, record_audit
from ..models import AccountAuthMethod, ConnectedAccount, ConnectionHealth, User
from ..schemas import ConnectAccountRequest, ConnectedAccountOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _apply_method(account: ConnectedAccount, payload: ConnectAccountRequest) -> None:
    account.auth_method = payload.auth_method
    account.display_name = payload.display_name or account.display_name

    if payload.auth_method == AccountAuthMethod.managed_business_page:
        # No client credentials; we set the page up for them.
        account.encrypted_session = None
        account.health = ConnectionHealth.provisioning
    elif payload.auth_method == AccountAuthMethod.oauth:
        # Real OAuth returns a token; the scaffold simulates a successful
        # authorization so no password is ever requested or stored.
        account.encrypted_session = encrypt(payload.credential or "oauth-authorized")
        account.health = ConnectionHealth.healthy
    else:  # session (advanced)
        account.encrypted_session = encrypt(payload.credential)
        account.health = ConnectionHealth.healthy


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
    account = existing or ConnectedAccount(
        user_id=user.id, provider=payload.provider
    )
    _apply_method(account, payload)
    if not existing:
        db.add(account)
    db.commit()
    db.refresh(account)
    record_audit(
        db,
        "account.connect",
        user_id=user.id,
        detail=f"{payload.provider.value} via {payload.auth_method.value}",
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
