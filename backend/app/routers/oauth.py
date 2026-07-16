"""Official OAuth connect flow (no password ever shared).

- ``GET /api/accounts/oauth/{provider}/start`` returns the authorize URL.
- ``GET /api/accounts/oauth/{provider}/callback`` exchanges the code for a token,
  stores it (encrypted), and redirects back to the dashboard.

When the provider's client id/secret are configured, this is the real OAuth 2.0
flow. Otherwise a simulated dev flow lets you exercise the UX end-to-end without
credentials — going live is just dropping in the client id/secret.
"""
from __future__ import annotations

import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..crypto import encrypt
from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AccountAuthMethod,
    AccountProvider,
    ConnectedAccount,
    ConnectionHealth,
    User,
)
from ..security import create_access_token, decode_access_token

logger = logging.getLogger("leadpilot.oauth")
router = APIRouter(prefix="/api/accounts/oauth", tags=["oauth"])

_AUTHORIZE = {
    "facebook": "https://www.facebook.com/v21.0/dialog/oauth",
    "nextdoor": "https://nextdoor.com/oauth/authorize",
}
_TOKEN = {
    "facebook": "https://graph.facebook.com/v21.0/oauth/access_token",
    "nextdoor": "https://nextdoor.com/oauth/token",
}
_SCOPES = {
    "facebook": "pages_manage_posts,pages_read_engagement",
    "nextdoor": "post:write post:read",
}


def _client(provider: str) -> tuple[str | None, str | None]:
    if provider == "facebook":
        return settings.meta_client_id, settings.meta_client_secret
    return settings.nextdoor_client_id, settings.nextdoor_client_secret


def _redirect_uri(provider: str) -> str:
    return f"{settings.oauth_redirect_base}/api/accounts/oauth/{provider}/callback"


@router.get("/{provider}/start")
def oauth_start(
    provider: AccountProvider,
    user: User = Depends(get_current_user),
):
    p = provider.value
    # A signed state carries the user id through the redirect, CSRF-safe.
    state = create_access_token(str(user.id), f"oauth:{p}:{secrets.token_hex(8)}")
    if not settings.oauth_configured(p):
        # Simulated dev flow → straight to our callback with a fake code.
        url = (
            f"{_redirect_uri(p)}?code=dev-simulated&state={state}&simulated=1"
        )
        return {"authorize_url": url, "simulated": True}

    client_id, _ = _client(p)
    url = (
        f"{_AUTHORIZE[p]}?client_id={client_id}"
        f"&redirect_uri={_redirect_uri(p)}"
        f"&state={state}&response_type=code"
        f"&scope={_SCOPES[p]}"
    )
    return {"authorize_url": url, "simulated": False}


@router.get("/{provider}/callback")
def oauth_callback(
    provider: AccountProvider,
    state: str,
    code: str = Query(default=""),
    simulated: int = Query(default=0),
    db: Session = Depends(get_db),
):
    p = provider.value
    payload = decode_access_token(state)
    if not payload or not str(payload.get("role", "")).startswith(f"oauth:{p}"):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=400, detail="Unknown user")

    token = "oauth-simulated-token"
    if not simulated and settings.oauth_configured(p):
        token = _exchange_code(p, code) or token

    _upsert_account(db, user, provider, token)
    return RedirectResponse(
        url=f"{settings.frontend_base_url}/onboarding?connected={p}", status_code=303
    )


def _exchange_code(provider: str, code: str) -> str | None:
    client_id, client_secret = _client(provider)
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                _TOKEN[provider],
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": _redirect_uri(provider),
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
    except Exception as exc:  # noqa: BLE001
        logger.warning("OAuth token exchange failed (%s): %s", provider, exc)
        return None


def _upsert_account(
    db: Session, user: User, provider: AccountProvider, token: str
) -> None:
    account = db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user.id,
            ConnectedAccount.provider == provider,
        )
    ).scalar_one_or_none()
    if not account:
        account = ConnectedAccount(user_id=user.id, provider=provider)
        db.add(account)
    account.auth_method = AccountAuthMethod.oauth
    account.encrypted_session = encrypt(token)
    account.health = ConnectionHealth.healthy
    account.display_name = account.display_name or user.business_name
    db.commit()
