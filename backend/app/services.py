"""Domain services: lead discovery pipeline and quota accounting."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import hashlib

from .ai.drafter import draft_reply
from .ai.matcher import classify_lead
from .ai.recruiter import generate_pitch
from .config import settings
from .connectors import connector_for
from .crypto import decrypt
from .models import (
    AccountProvider,
    AgentResponse,
    ClientPricingProfile,
    LeadMatch,
    LeadStatus,
    OutreachRecruit,
    ResponseStatus,
    Subscription,
    SubscriptionStatus,
    User,
    UserRole,
)
from .plans import DEFAULT_PLAN_CODE, get_plan


def _split(csv: str | None) -> list[str]:
    return [s.strip() for s in (csv or "").split(",") if s.strip()]


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def subscription_active(user: User) -> bool:
    """Whether the user currently has access: active plan, or an unexpired trial.

    Enforced live (a trial whose end date has passed is inactive even before the
    nightly expiry job flips its stored status)."""
    sub = user.subscription
    if not sub:
        return False
    if sub.status == SubscriptionStatus.active:
        return True
    if sub.status == SubscriptionStatus.trialing:
        return sub.trial_end is None or sub.trial_end > _utcnow_naive()
    return False


def create_trial_user(
    db: Session,
    *,
    email: str,
    business_name: str | None = None,
    phone: str | None = None,
    nextdoor_handle: str | None = None,
    plan_code: str | None = None,
    source: str = "self",
) -> tuple[User, bool]:
    """Create a profile-based, passwordless trial account. Returns (user, created).

    If a user with this email already exists, returns it unchanged.
    """
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        return existing, False

    plan = get_plan(plan_code) or get_plan(DEFAULT_PLAN_CODE)
    user = User(
        email=email,
        password_hash=None,  # passwordless — magic-link login
        role=UserRole.provider,
        business_name=business_name,
        phone=phone,
        nextdoor_handle=nextdoor_handle,
        onboarding_source=source,
    )
    user.subscription = Subscription(
        plan_code=plan.code if plan else DEFAULT_PLAN_CODE,
        status=SubscriptionStatus.trialing,
        trial_end=datetime.now(timezone.utc) + timedelta(days=7),
    )
    user.pricing_profile = ClientPricingProfile(phone=phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, True


def on_trial(user: User) -> bool:
    return bool(
        user.subscription
        and user.subscription.status == SubscriptionStatus.trialing
    )


def daily_quota(user: User) -> int:
    # During the free trial, everyone is capped to a single reply per day,
    # regardless of the plan they selected for after the trial.
    if on_trial(user):
        return settings.trial_daily_post_quota
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

    # Only pull from platforms the client has actually connected. Map each
    # provider to its (decrypted) credential so we can build the right connector.
    accounts = {a.provider.value: a for a in user.connected_accounts}
    if not accounts:
        # No connected accounts yet — demo against the sample source on both.
        targets = {AccountProvider.facebook.value: None, AccountProvider.nextdoor.value: None}
    else:
        targets = {p: decrypt(a.encrypted_session) for p, a in accounts.items()}

    created: list[LeadMatch] = []
    for provider_value, credential in targets.items():
        connector = connector_for(provider_value, credential=credential)
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


# A small pool of "other providers" the recruiter might discover. A real
# implementation would source these from the connected platforms' public posts.
_RECRUIT_POOL = [
    {"name": "Ace Drain Solutions", "trade": "plumbing", "url": "https://example.test/p/ace-drain"},
    {"name": "GreenBlade Lawncare", "trade": "landscaping", "url": "https://example.test/p/greenblade"},
    {"name": "Sparkle Home Cleaning", "trade": "house cleaning", "url": "https://example.test/p/sparkle"},
    {"name": "TruCoat Painters", "trade": "painting", "url": "https://example.test/p/trucoat"},
    {"name": "Handy Hank", "trade": "handyman services", "url": "https://example.test/p/handy-hank"},
    {"name": "RapidFlow Plumbing", "trade": "plumbing", "url": "https://example.test/p/rapidflow"},
]


def run_recruiting(db: Session, *, limit: int = 5) -> list[OutreachRecruit]:
    """Discover other local providers and queue a personalized trial pitch.

    Persists one ``OutreachRecruit`` per new target with the generated message.
    Delivery is gated by ``LEADPILOT_LIVE_CONNECTORS`` and consent controls; in
    the scaffold we mark the message as queued/sent for the demo.
    """
    created: list[OutreachRecruit] = []
    for item in _RECRUIT_POOL[:limit]:
        dedup = hashlib.sha256(item["url"].encode()).hexdigest()[:32]
        exists = db.execute(
            select(OutreachRecruit.id).where(OutreachRecruit.dedup_key == dedup)
        ).first()
        if exists:
            continue
        generate_pitch(name=item["name"], trade=item["trade"])  # copy generated
        recruit = OutreachRecruit(
            provider=AccountProvider.facebook,
            profile_url=item["url"],
            contact_name=item["name"],
            message_sent=True,
            dedup_key=dedup,
        )
        db.add(recruit)
        created.append(recruit)
    db.commit()
    return created
