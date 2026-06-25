"""Business Posts (broadcast).

The compliant, automatable way for the AI to post on Nextdoor: compose a new
Business Post and publish it via the official Create Post API (there is no reply
API). Also works for Facebook Page posts. Drafts are reviewed before publishing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.broadcaster import compose_business_post
from ..config import settings
from ..connectors import connector_for, provider_capabilities
from ..crypto import decrypt
from ..database import get_db
from ..deps import get_current_user, record_audit
from ..models import (
    AccountProvider,
    BroadcastPost,
    BroadcastStatus,
    ConnectedAccount,
    User,
)
from ..schemas import (
    BroadcastDraftRequest,
    BroadcastEditRequest,
    BroadcastOut,
    BroadcastScheduleRequest,
)

router = APIRouter(prefix="/api/broadcast", tags=["broadcast"])


def _too_soon(db: Session, user_id: int, provider: AccountProvider) -> datetime | None:
    """Return the earliest allowed next-post time if within the cooldown window.

    Platforms (Nextdoor especially) limit Business Post frequency; we enforce a
    safe minimum interval between posted broadcasts per platform.
    """
    last = db.execute(
        select(BroadcastPost.posted_at)
        .where(
            BroadcastPost.user_id == user_id,
            BroadcastPost.provider == provider,
            BroadcastPost.status == BroadcastStatus.posted,
            BroadcastPost.posted_at.is_not(None),
        )
        .order_by(BroadcastPost.posted_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not last:
        return None
    window = timedelta(hours=settings.broadcast_min_interval_hours)
    next_allowed = last + window
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return next_allowed if next_allowed > now else None


def _do_publish(db: Session, post: BroadcastPost) -> bool:
    account = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.user_id == post.user_id,
            ConnectedAccount.provider == post.provider,
        )
        .first()
    )
    credential = decrypt(account.encrypted_session) if account else None
    connector = connector_for(post.provider.value, credential=credential)
    ok = connector.broadcast(body_text=post.body_text)
    if ok:
        post.status = BroadcastStatus.posted
        post.posted_at = datetime.now(timezone.utc)
    else:
        post.status = BroadcastStatus.failed
    db.commit()
    return ok


@router.get("", response_model=list[BroadcastOut])
def list_broadcasts(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    stmt = (
        select(BroadcastPost)
        .where(BroadcastPost.user_id == user.id)
        .order_by(BroadcastPost.created_at.desc())
    )
    return db.execute(stmt).scalars().all()


@router.post("/draft", response_model=BroadcastOut, status_code=201)
def draft_broadcast(
    payload: BroadcastDraftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not provider_capabilities(payload.provider.value)["broadcast"]:
        raise HTTPException(
            status_code=400, detail=f"{payload.provider.value} does not support broadcasts"
        )
    text = compose_business_post(
        user.business_name or "a local pro", user.pricing_profile, topic=payload.topic
    )
    post = BroadcastPost(
        user_id=user.id, provider=payload.provider, body_text=text
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def _load_owned(post_id: int, user: User, db: Session) -> BroadcastPost:
    post = db.get(BroadcastPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return post


@router.put("/{post_id}", response_model=BroadcastOut)
def edit_broadcast(
    post_id: int,
    payload: BroadcastEditRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = _load_owned(post_id, user, db)
    if post.status == BroadcastStatus.posted:
        raise HTTPException(status_code=409, detail="Already posted")
    post.body_text = payload.body_text
    db.commit()
    db.refresh(post)
    return post


@router.post("/{post_id}/schedule", response_model=BroadcastOut)
def schedule_broadcast(
    post_id: int,
    payload: BroadcastScheduleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = _load_owned(post_id, user, db)
    if post.status == BroadcastStatus.posted:
        raise HTTPException(status_code=409, detail="Already posted")
    when = payload.scheduled_for
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    post.scheduled_for = when
    post.status = BroadcastStatus.scheduled
    db.commit()
    db.refresh(post)
    return post


@router.post("/{post_id}/publish", response_model=BroadcastOut)
def publish_broadcast(
    post_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = _load_owned(post_id, user, db)
    if post.status == BroadcastStatus.posted:
        raise HTTPException(status_code=409, detail="Already posted")

    blocked_until = _too_soon(db, user.id, post.provider)
    if blocked_until:
        raise HTTPException(
            status_code=429,
            detail=(
                f"To stay within {post.provider.value}'s posting limits, the next "
                f"Business Post can go out after {blocked_until:%Y-%m-%d %H:%M} UTC."
            ),
        )

    if not _do_publish(db, post):
        raise HTTPException(status_code=502, detail="Failed to publish broadcast")
    db.refresh(post)
    record_audit(
        db,
        "broadcast.post",
        user_id=user.id,
        detail=f"broadcast={post.id} provider={post.provider.value}",
        request=request,
    )
    return post


def publish_due_broadcasts(db: Session) -> int:
    """Publish scheduled broadcasts whose time has arrived (called by scheduler).

    Respects the per-platform frequency guard; posts that are still inside the
    cooldown are left scheduled and retried on the next tick.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    due = (
        db.execute(
            select(BroadcastPost).where(
                BroadcastPost.status == BroadcastStatus.scheduled,
                BroadcastPost.scheduled_for.is_not(None),
                BroadcastPost.scheduled_for <= now,
            )
        )
        .scalars()
        .all()
    )
    published = 0
    for post in due:
        if _too_soon(db, post.user_id, post.provider):
            continue
        if _do_publish(db, post):
            published += 1
    return published


@router.delete("/{post_id}", status_code=204)
def delete_broadcast(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = _load_owned(post_id, user, db)
    db.delete(post)
    db.commit()
