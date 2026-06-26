"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    AccountAuthMethod,
    AccountProvider,
    BroadcastStatus,
    ConnectionHealth,
    LeadStatus,
    ResponseStatus,
    SubscriptionStatus,
    TicketStatus,
    UserRole,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth -------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    business_name: str | None = None
    plan_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class StartTrialRequest(BaseModel):
    """Profile-based, passwordless trial signup (e.g. captured by the onboarding
    AI after a prospect accepts a trial)."""

    email: EmailStr
    name: str | None = None
    business_name: str | None = None
    phone: str | None = None
    nextdoor_handle: str | None = None
    plan_code: str | None = None
    recruit_id: int | None = None


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicVerifyRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Users / profile --------------------------------------------------------
class UserOut(ORMModel):
    id: int
    email: EmailStr
    role: UserRole
    business_name: str | None
    contact_name: str | None
    phone: str | None
    nextdoor_handle: str | None
    onboarding_source: str
    timezone: str
    automation_enabled: bool
    sms_enabled: bool


class SubscriptionOut(ORMModel):
    plan_code: str
    status: SubscriptionStatus
    trial_end: datetime | None


class AccountUpdateRequest(BaseModel):
    business_name: str | None = None
    phone: str | None = None
    timezone: str | None = None
    nextdoor_handle: str | None = None
    sms_enabled: bool | None = None


class PasswordSetRequest(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8)


class PricingProfileIn(BaseModel):
    trade: str | None = None
    service_categories: list[str] = []
    price_list: str = ""
    phone: str | None = None
    target_neighborhoods: list[str] = []


class PricingProfileOut(BaseModel):
    trade: str | None
    service_categories: list[str]
    price_list: str
    phone: str | None
    target_neighborhoods: list[str]


class PlanOut(BaseModel):
    code: str
    name: str
    price_monthly: int
    daily_post_quota: int


# --- Connected accounts -----------------------------------------------------
class ConnectAccountRequest(BaseModel):
    provider: AccountProvider
    auth_method: AccountAuthMethod = AccountAuthMethod.oauth
    display_name: str | None = None
    # Only used for the `session` (advanced) method. OAuth/managed need no
    # credential from the client.
    credential: str | None = None


class ConnectedAccountOut(ORMModel):
    id: int
    provider: AccountProvider
    auth_method: AccountAuthMethod
    display_name: str | None
    health: ConnectionHealth
    connected_at: datetime


# --- Leads & responses ------------------------------------------------------
class AgentResponseOut(ORMModel):
    id: int
    generated_text: str
    status: ResponseStatus
    posted_at: datetime | None


class LeadOut(ORMModel):
    id: int
    provider: AccountProvider
    post_url: str | None
    author: str | None
    content: str
    location: str | None
    status: LeadStatus
    relevance_score: float | None
    relevance_reason: str | None
    created_at: datetime
    response: AgentResponseOut | None = None


class QuotaOut(BaseModel):
    plan_code: str
    daily_quota: int
    used_today: int
    remaining_today: int
    on_trial: bool = False


class DraftEditRequest(BaseModel):
    generated_text: str


# --- Subscription -----------------------------------------------------------
class SelectPlanRequest(BaseModel):
    plan_code: str


class SelectPlanResponse(BaseModel):
    subscription: SubscriptionOut
    checkout_url: str | None = None


# --- Support ----------------------------------------------------------------
class SupportMessageOut(ORMModel):
    role: str
    content: str
    created_at: datetime


class SupportChatRequest(BaseModel):
    ticket_id: int | None = None
    message: str


class SupportChatResponse(BaseModel):
    ticket_id: int
    reply: str
    escalated: bool


class TicketOut(ORMModel):
    id: int
    status: TicketStatus
    escalated: bool
    created_at: datetime
    messages: list[SupportMessageOut] = []


# --- Admin ------------------------------------------------------------------
class AdminUserOut(ORMModel):
    id: int
    email: EmailStr
    business_name: str | None
    role: UserRole
    automation_enabled: bool
    created_at: datetime
    subscription: SubscriptionOut | None = None


class AuditLogOut(ORMModel):
    id: int
    user_id: int | None
    action: str
    detail: str | None
    created_at: datetime


# --- Broadcast (Business Posts) ---------------------------------------------
class BroadcastOut(ORMModel):
    id: int
    provider: AccountProvider
    body_text: str
    status: BroadcastStatus
    scheduled_for: datetime | None
    posted_at: datetime | None
    created_at: datetime


class BroadcastDraftRequest(BaseModel):
    provider: AccountProvider = AccountProvider.nextdoor
    topic: str | None = None


class BroadcastEditRequest(BaseModel):
    body_text: str


class BroadcastScheduleRequest(BaseModel):
    scheduled_for: datetime


class RecruitOut(ORMModel):
    id: int
    provider: AccountProvider
    profile_url: str | None
    contact_name: str | None
    email: str | None
    phone: str | None
    nextdoor_handle: str | None
    converted_user_id: int | None
    message_sent: bool
    trial_signup_at: datetime | None
    created_at: datetime


class ConvertRecruitRequest(BaseModel):
    email: EmailStr
    business_name: str | None = None
    phone: str | None = None
    nextdoor_handle: str | None = None
    plan_code: str | None = None


class NotificationOut(ORMModel):
    id: int
    kind: str
    title: str
    body: str
    read: bool
    created_at: datetime


class ManagedAccountOut(BaseModel):
    id: int
    provider: AccountProvider
    auth_method: AccountAuthMethod
    health: ConnectionHealth
    business_name: str | None
    email: EmailStr
    connected_at: datetime


# --- Admin: client CRM ------------------------------------------------------
class ClientContactIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class ClientContactOut(BaseModel):
    id: int
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class ClientSummary(BaseModel):
    id: int
    business_name: str | None
    contact_name: str | None
    city: str | None
    state: str | None
    client_status: str
    claimed_by: str | None
    plan_code: str | None
    trial_active: bool
    trial_days_left: int | None


class ClientDetail(BaseModel):
    id: int
    email: EmailStr
    business_name: str | None
    contact_name: str | None
    phone: str | None
    city: str | None
    state: str | None
    service_radius_miles: int | None
    client_notes: str | None
    bot_notes: str | None
    claimed_by: str | None
    client_status: str
    trade: str | None
    services: list[str]
    plan_code: str | None
    trial_active: bool
    trial_days_left: int | None
    trial_end: datetime | None
    contacts: list[ClientContactOut]


class ClientUpdate(BaseModel):
    business_name: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    service_radius_miles: int | None = None
    client_notes: str | None = None
    bot_notes: str | None = None
    claimed_by: str | None = None
    client_status: str | None = None
    trade: str | None = None
    services: list[str] | None = None


class TrialUpdate(BaseModel):
    days_left: int | None = None
    trial_active: bool | None = None
