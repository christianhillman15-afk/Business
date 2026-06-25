"""Business Posts (broadcast).

The compliant, automatable way for the AI to post on Nextdoor: compose a new
Business Post and publish it via the official Create Post API (there is no reply
API). Also works for Facebook Page posts. Drafts are reviewed before publishing.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.broadcaster import compose_business_post
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
from ..schemas import BroadcastDraftRequest, BroadcastEditRequest, BroadcastOut

router = APIRouter(prefix="/api/broadcast", tags=["broadcast"])


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

    account = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.user_id == user.id,
            ConnectedAccount.provider == post.provider,
        )
        .first()
    )
    credential = decrypt(account.encrypted_session) if account else None
    connector = connector_for(post.provider.value, credential=credential)
    ok = connector.broadcast(body_text=post.body_text)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to publish broadcast")

    post.status = BroadcastStatus.posted
    post.posted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)
    record_audit(
        db,
        "broadcast.post",
        user_id=user.id,
        detail=f"broadcast={post.id} provider={post.provider.value}",
        request=request,
    )
    return post


@router.delete("/{post_id}", status_code=204)
def delete_broadcast(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = _load_owned(post_id, user, db)
    db.delete(post)
    db.commit()
