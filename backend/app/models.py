"""SQLAlchemy ORM models — the LeadPilot data entities."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    provider = "provider"  # DIY service provider (the paying customer)
    admin = "admin"  # platform administrator / support


class SubscriptionStatus(str, enum.Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"


class AccountProvider(str, enum.Enum):
    facebook = "facebook"
    nextdoor = "nextdoor"


class ConnectionHealth(str, enum.Enum):
    healthy = "healthy"
    needs_reauth = "needs_reauth"
    disconnected = "disconnected"
    provisioning = "provisioning"  # managed business page being set up


class AccountAuthMethod(str, enum.Enum):
    # Official authorization flow — the client authorizes us; no password shared.
    oauth = "oauth"
    # LeadPilot provisions and operates a dedicated Business Page for the client.
    # No personal account or credentials are involved.
    managed_business_page = "managed_business_page"
    # Advanced: a captured session token (encrypted at rest). Discouraged.
    session = "session"


class LeadStatus(str, enum.Enum):
    new = "new"  # discovered, relevance not yet decided
    matched = "matched"  # AI judged it relevant to the client's trade
    irrelevant = "irrelevant"  # AI judged it out of the client's field
    drafted = "drafted"  # a reply draft exists
    engaged = "engaged"  # a reply was posted
    dismissed = "dismissed"  # client dismissed it


class ResponseStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    posted = "posted"
    rejected = "rejected"


class TicketStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Nullable: profile-based accounts (recruited via trial) have no password and
    # sign in with a magic link instead.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.provider
    )
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nextdoor_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onboarding_source: Mapped[str] = mapped_column(String(40), default="self")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    subscription: Mapped["Subscription"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    pricing_profile: Mapped["ClientPricingProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    connected_accounts: Mapped[list["ConnectedAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    leads: Mapped[list["LeadMatch"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tickets: Mapped[list["SupportTicket"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    plan_code: Mapped[str] = mapped_column(String(32), default="growth")
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.trialing
    )
    trial_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="subscription")


class ClientPricingProfile(Base):
    __tablename__ = "client_pricing_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    # The client's trade, e.g. "plumbing", "house cleaning", "landscaping".
    trade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Comma-separated service categories / keywords that define what's in-field.
    service_categories: Mapped[str] = mapped_column(Text, default="")
    price_list: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Comma-separated neighborhoods / cities to target.
    target_neighborhoods: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="pricing_profile")


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[AccountProvider] = mapped_column(Enum(AccountProvider))
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_method: Mapped[AccountAuthMethod] = mapped_column(
        Enum(AccountAuthMethod), default=AccountAuthMethod.oauth
    )
    # Encrypted OAuth token / session blob. None for managed business pages.
    encrypted_session: Mapped[str | None] = mapped_column(Text, nullable=True)
    health: Mapped[ConnectionHealth] = mapped_column(
        Enum(ConnectionHealth), default=ConnectionHealth.healthy
    )
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="connected_accounts")


class LeadMatch(Base):
    __tablename__ = "lead_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[AccountProvider] = mapped_column(Enum(AccountProvider))
    post_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Deduplication key so the same post is never engaged twice for a client.
    dedup_key: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus), default=LeadStatus.new
    )
    # AI relevance: is this post in the client's trade?
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="leads")
    response: Mapped["AgentResponse"] = relationship(
        back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )


class AgentResponse(Base):
    __tablename__ = "agent_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("lead_matches.id"), unique=True)
    generated_text: Mapped[str] = mapped_column(Text)
    status: Mapped[ResponseStatus] = mapped_column(
        Enum(ResponseStatus), default=ResponseStatus.draft
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    lead: Mapped[LeadMatch] = relationship(back_populates="response")


class OutreachRecruit(Base):
    """A target service provider the recruiting pipeline reached out to."""

    __tablename__ = "outreach_recruits"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[AccountProvider] = mapped_column(Enum(AccountProvider))
    profile_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Contact details the onboarding AI collects when a prospect accepts a trial.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nextdoor_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    converted_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    message_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_signup_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.open
    )
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="tickets")
    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportMessage.created_at",
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"))
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    ticket: Mapped[SupportTicket] = relationship(back_populates="messages")


class BroadcastStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    posted = "posted"
    failed = "failed"


class BroadcastPost(Base):
    """A proactive 'Business Post' the client publishes to nearby neighbors.

    On Nextdoor this maps to the official Create Post API (no reply API exists);
    on Facebook, to a Page feed post. Composed by AI, published on approval.
    """

    __tablename__ = "broadcast_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[AccountProvider] = mapped_column(Enum(AccountProvider))
    body_text: Mapped[str] = mapped_column(Text)
    status: Mapped[BroadcastStatus] = mapped_column(
        Enum(BroadcastStatus), default=BroadcastStatus.draft
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
