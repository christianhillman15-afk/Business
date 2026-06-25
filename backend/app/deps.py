"""Shared FastAPI dependencies: current user, role guards, audit logging."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLog, User, UserRole
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise credentials_exc
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise credentials_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user


def record_audit(
    db: Session,
    action: str,
    *,
    user_id: int | None = None,
    detail: str | None = None,
    request: Request | None = None,
) -> None:
    ip = request.client.host if request and request.client else None
    db.add(AuditLog(user_id=user_id, action=action, detail=detail, ip_address=ip))
    db.commit()
