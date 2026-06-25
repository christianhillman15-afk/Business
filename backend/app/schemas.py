"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    AccountProvider,
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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Users / profile --------------------------------------------------------
class UserOut(ORMModel):
    id: int
    email: EmailStr
    role: UserRole
    business_name: str | None
    timezone: str
    automation_enabled: bool


class SubscriptionOut(ORMModel):
    plan_code: str
    status: SubscriptionStatus
    trial_end: datetime | None


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
    display_name: str | None = None
    # In the real product this is an OAuth code / captured session. The stub
    # accepts any opaque token to simulate a successful connection.
    credential: str | None = None


class ConnectedAccountOut(ORMModel):
    id: int
    provider: AccountProvider
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


class DraftEditRequest(BaseModel):
    generated_text: str


# --- Subscription -----------------------------------------------------------
class SelectPlanRequest(BaseModel):
    plan_code: str


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
