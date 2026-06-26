"""Notification helper: records an in-app notification and, by default, also
texts it to the customer (LeadPilot is SMS-first)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .email import send_email
from .models import Notification, User, UserRole
from .sms import send_sms


def notify(
    db: Session,
    user: User,
    *,
    kind: str,
    title: str,
    body: str = "",
    email: bool = False,
    sms: bool = True,
) -> Notification:
    """Record an in-app notification and, unless ``sms=False``, text it to the
    customer when they have a phone number and haven't opted out."""
    n = Notification(user_id=user.id, kind=kind, title=title, body=body)
    db.add(n)
    db.commit()
    db.refresh(n)
    if email:
        send_email(user.email, title, body or title)
    if (
        sms
        and user.phone
        and user.sms_enabled
        and getattr(user, "client_status", "enabled") != "disabled"
    ):
        send_sms(user.phone, f"{title}\n{body}".strip())
    return n


def notify_admins(db: Session, *, kind: str, title: str, body: str = "") -> None:
    admins = (
        db.execute(select(User).where(User.role == UserRole.admin)).scalars().all()
    )
    for admin in admins:
        db.add(Notification(user_id=admin.id, kind=kind, title=title, body=body))
        send_email(admin.email, title, body or title)
    db.commit()
