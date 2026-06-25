# LeadPilot Architecture

## Overview

LeadPilot is a multi-tenant SaaS for local service businesses. Three engines,
mirroring the product spec:

1. **Client Portal & Dashboard** — register, connect accounts, choose a tier,
   review field-matched leads and AI draft replies, watch the daily quota.
2. **Discovery & Engagement Engine** — scans local feeds, classifies each post
   against the client's trade (field-matching), and drafts a contextual reply.
3. **Acquisition & Support Engine** — the in-app AI support chatbot (with human
   escalation) and the recruiting data model. (The recruiting *runner* is a
   future phase; the data entity and admin log exist today.)

```
Next.js dashboard ── HTTP/JSON ──▶ FastAPI API
                                     │
        ┌────────────────────────────┼─────────────────────────────┐
        ▼                            ▼                              ▼
  Auth / Billing            Discovery pipeline               Support chatbot
  (JWT, tiered plans)   (connector → matcher → drafter)     (Claude + escalate)
        │                            │                              │
        └──────────── SQLAlchemy / SQLite|Postgres ─────────────────┘
                                     │
                        Anthropic Claude (optional)
```

## Backend (`backend/app`)

| Module | Responsibility |
|--------|----------------|
| `config.py` | Settings from env / `.env` |
| `database.py` | Engine, session, `init_db()` |
| `models.py` | ORM entities (User, Subscription, ClientPricingProfile, ConnectedAccount, LeadMatch, AgentResponse, OutreachRecruit, SupportTicket, AuditLog) |
| `schemas.py` | Pydantic request/response models |
| `security.py` | Password hashing (PBKDF2) + JWT |
| `deps.py` | Current-user / admin guards, audit logging |
| `plans.py` | The five tiers ($200/1 → $400/8 posts per day) |
| `crypto.py` | AES-256-GCM encryption of connected sessions at rest |
| `billing.py` | Stripe Checkout + webhook, with a mock provider fallback |
| `services.py` | Discovery pipeline, quota accounting, recruiting pipeline |
| `tasks.py` | Scheduled / CLI jobs (`discover_all`, `recruit`) + APScheduler |
| `ai/` | `client` (Claude wrapper), `matcher` (field-matching), `drafter` (replies), `support` (chatbot), `recruiter` (trial pitches), `broadcaster` (Business Posts) |
| `connectors/` | `connector_for` factory + `provider_capabilities`; Meta Graph + **Nextdoor** connectors + sample source. See [`NEXTDOOR.md`](NEXTDOOR.md) |
| `routers/` | API endpoints |

### The discovery pipeline (`services.run_discovery`)

```
for each connected platform:
    posts = connector.discover(neighborhoods)        # compliant source
    for post not already seen (dedup_key):
        match = classify_lead(post, trade, categories)   # AI field-matching
        store LeadMatch(status = matched | irrelevant)
        if match.is_relevant:
            draft = draft_reply(lead, pricing_profile)    # AI reply
            store AgentResponse(status = draft)           # awaits approval
```

Only **in-field** posts get a draft. Posting is **human-in-the-loop** and
**quota-enforced** (`responses.approve_and_post`).

### AI layer

Uses the Anthropic SDK (`claude-opus-4-8` for drafting/support,
`claude-haiku-4-5` for high-volume classification). Every AI call has a
deterministic offline fallback, so the app runs with no API key. Field-matching
uses structured outputs (`output_config.format`) for a reliable
`{is_relevant, score, reason}` verdict.

## Frontend (`frontend/app`)

Next.js 14 App Router, client-rendered pages calling the API with a bearer
token in `localStorage`.

| Route | Purpose |
|-------|---------|
| `/login`, `/register` | Auth |
| `/dashboard` | Quota, scan, in-field leads, draft review/approve/edit/reject |
| `/onboarding` | Connect accounts + trade/pricing profile |
| `/billing` | Tier selection |
| `/support` | AI support chat |
| `/admin` | Platform stats, clients, audit trail |

## Data store

SQLite by default (zero-config dev). Set `DATABASE_URL` to a PostgreSQL DSN for
production. Models are plain SQLAlchemy; add Alembic for migrations when moving
beyond `create_all`.

## Lifecycle & infra modules

| Module | Responsibility |
|--------|----------------|
| `email.py` | Transactional email (console default; SMTP/Mailgun when configured) |
| `notifications.py` | In-app notifications + optional email; `notify` / `notify_admins` |
| `routers/oauth.py` | Official OAuth connect (real when client id/secret set; simulated dev flow otherwise) |
| `routers/notifications.py` | List / unread-count / mark-read endpoints |
| `alembic/` | Database migrations (`alembic upgrade head`); Docker runs this on boot |

Notifications fire on: welcome, plan/billing receipt, reply posted, quota
exhausted, support escalation (to admins), and managed-page activation.

Business Posts can be **scheduled** (`/api/broadcast/{id}/schedule`) and are
published by the scheduler, subject to a per-platform **frequency guard**
(`BROADCAST_MIN_INTERVAL_HOURS`) so you stay within Nextdoor's posting limits.

## Done since the first scaffold

- **Argon2id** password hashing (PBKDF2 fallback kept for portability).
- **AES-256-GCM** encryption of connected sessions (`crypto.py`).
- **Stripe** Checkout + webhook activation (`billing.py`), mock provider when no key.
- **Scheduled discovery** via APScheduler + CLI (`tasks.py`).
- **Trial Recruiter** engine (`ai/recruiter.py` + admin endpoints).
- **Meta Graph API** Facebook connector (`connectors/meta.py`), gated by
  `LEADPILOT_LIVE_CONNECTORS`.
- **Test suite** (`tests/`) covering the core flows.

## Still recommended before production

- A durable job queue (Celery/RQ + Redis) if discovery volume grows beyond the
  in-process scheduler.
- Rate limiting, structured logging, per-account pacing, and Meta app review for
  the live connector — **read [`COMPLIANCE.md`](COMPLIANCE.md) first.**
- A real Nextdoor integration path (no public API today).
