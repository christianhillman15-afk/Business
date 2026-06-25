"""Domain services: lead discovery pipeline and quota accounting."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ai.drafter import draft_reply
from .ai.matcher import classify_lead
from .connectors import CONNECTORS
from .models import (
    AccountProvider,
    AgentResponse,
    LeadMatch,
    LeadStatus,
    ResponseStatus,
    User,
)
from .plans import DEFAULT_PLAN_CODE, get_plan


def _split(csv: str | None) -> list[str]:
    return [s.strip() for s in (csv or "").split(",") if s.strip()]


def daily_quota(user: User) -> int:
    plan = get_plan(user.subscription.plan_code if user.subscription else None)
    plan = plan or get_plan(DEFAULT_PLAN_CODE)
    return plan.daily_post_quota if plan else 4


def posts_used_today(db: Session, user: User) -> int:
    """Count replies posted since local midnight (approximated via timezone)."""
    start = _local_midnight_utc(user.timezone)
    stmt = (
        select(func.count(AgentResponse.id))
        .join(LeadMatch, AgentResponse.lead_id == LeadMatch.id)
        .where(
            LeadMatch.user_id == user.id,
            AgentResponse.status == ResponseStatus.posted,
            AgentResponse.posted_at >= start,
        )
    )
    return int(db.execute(stmt).scalar_one())


def remaining_quota(db: Session, user: User) -> int:
    return max(0, daily_quota(user) - posts_used_today(db, user))


def _local_midnight_utc(tz_name: str) -> datetime:
    """Best-effort local midnight as a UTC datetime (zoneinfo if available)."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name)
        now_local = datetime.now(tz)
        midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight_local.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:  # noqa: BLE001
        return (datetime.now(timezone.utc) - timedelta(hours=24)).replace(tzinfo=None)


def run_discovery(db: Session, user: User, *, limit: int = 6) -> list[LeadMatch]:
    """Discover candidate posts, classify them against the client's trade, and
    persist new leads. Relevant leads get an AI-drafted reply ready for review.
    """
    profile = user.pricing_profile
    trade = profile.trade if profile else None
    categories = _split(profile.service_categories if profile else "")
    neighborhoods = _split(profile.target_neighborhoods if profile else "")

    # Only pull from platforms the client has actually connected.
    connected = {a.provider.value for a in user.connected_accounts}
    if not connected:
        connected = {AccountProvider.facebook.value, AccountProvider.nextdoor.value}

    created: list[LeadMatch] = []
    for provider_value in connected:
        connector = CONNECTORS.get(provider_value)
        if not connector:
            continue
        for cand in connector.discover(neighborhoods=neighborhoods, limit=limit):
            dedup = cand.dedup_key(user.id)
            exists = db.execute(
                select(LeadMatch.id).where(
                    LeadMatch.user_id == user.id, LeadMatch.dedup_key == dedup
                )
            ).first()
            if exists:
                continue

            match = classify_lead(
                post_content=cand.content,
                trade=trade,
                service_categories=categories,
            )
            lead = LeadMatch(
                user_id=user.id,
                provider=AccountProvider(provider_value),
                post_url=cand.post_url,
                author=cand.author,
                content=cand.content,
                location=cand.location,
                dedup_key=dedup,
                relevance_score=match.score,
                relevance_reason=match.reason,
                status=LeadStatus.matched if match.is_relevant else LeadStatus.irrelevant,
            )
            db.add(lead)
            db.flush()  # assign lead.id

            if match.is_relevant:
                text = draft_reply(lead, profile)
                db.add(AgentResponse(lead_id=lead.id, generated_text=text))
                lead.status = LeadStatus.drafted

            created.append(lead)

    db.commit()
    return created
