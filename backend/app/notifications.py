"""Notification helper: creates an in-app notification and optionally emails it."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .email import send_email
from .models import Notification, User, UserRole


def notify(
    db: Session,
    user: User,
    *,
    kind: str,
    title: str,
    body: str = "",
    email: bool = False,
) -> Notification:
    n = Notification(user_id=user.id, kind=kind, title=title, body=body)
    db.add(n)
    db.commit()
    db.refresh(n)
    if email:
        send_email(user.email, title, body or title)
    return n


def notify_admins(db: Session, *, kind: str, title: str, body: str = "") -> None:
    admins = (
        db.execute(select(User).where(User.role == UserRole.admin)).scalars().all()
    )
    for admin in admins:
        db.add(Notification(user_id=admin.id, kind=kind, title=title, body=body))
        send_email(admin.email, title, body or title)
    db.commit()
