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
| `plans.py` | The four tiers ($250/4 → $400/10) |
| `services.py` | Discovery pipeline + quota accounting |
| `ai/` | `client` (Claude wrapper), `matcher` (field-matching), `drafter` (replies), `support` (chatbot) |
| `connectors/` | Pluggable social connectors + sample data source |
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

## Production hardening checklist (not done in the scaffold)

- Swap PBKDF2 → **Argon2id** for password hashing (the spec calls for Argon2).
- Encrypt connected-account sessions with **AES-256** in a real vault (the stub
  stores only an opaque marker).
- Real **Stripe** checkout + webhooks (mock provider is built in).
- Background workers (Celery/RQ) for scheduled discovery instead of the
  on-demand "Scan" button.
- Rate limiting, structured logging, and per-account pacing in the connectors.
- Real Facebook / Nextdoor connectors — **read [`COMPLIANCE.md`](COMPLIANCE.md)
  first.**
