# LeadPilot

An AI-powered lead-discovery and outreach platform for local service businesses
(plumbers, cleaners, landscapers, painters, etc.).

LeadPilot connects a service provider's social accounts, watches local
community feeds for people asking for the kind of work the provider does, and
uses AI to draft a tailored, on-brand reply containing the provider's services,
pricing, and contact details. Drafts are reviewed and approved by the provider
before anything is posted (human-in-the-loop), which keeps connected accounts
safe and the whole operation defensible.

It also includes tiered Stripe-style billing, an in-app AI support chatbot, and
an admin console.

> This repository is the **runnable foundation** described in
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The social-platform connectors
> ship as pluggable stubs with a sample data source so the whole product runs
> end-to-end without external credentials. Read
> [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) before wiring up real Facebook /
> Nextdoor integrations — it explains what's safe to build and what will get
> your customers' accounts banned.

---

## What's in the box

| Layer | Tech | Status |
|-------|------|--------|
| Client dashboard, onboarding wizard, admin console | Next.js 14 (App Router), React, Tailwind, TypeScript | ✅ runnable |
| API, auth, billing, lead/CRM model | FastAPI, SQLAlchemy, JWT | ✅ runnable |
| AI: **field-matching**, reply drafting, support chatbot | Anthropic Claude (`claude-opus-4-8`) | ✅ runnable, graceful offline fallback |
| Database | SQLite (dev) / PostgreSQL (prod) | ✅ runnable |
| Social connectors (Facebook / Nextdoor) | Pluggable interface + sample source | 🔌 stubbed |

The headline feature — **the bot only engages posts that genuinely fall within
the client's trade** — is implemented as a first-class AI relevance classifier
(`backend/app/ai/matcher.py`). A plumber's bot replies to plumbing leads, not
cleaning leads.

---

## Quick start

### Option A — Docker (everything at once)

```bash
cp .env.example .env          # optional: add ANTHROPIC_API_KEY for real AI
docker compose up --build
```

- Dashboard: http://localhost:3000
- API + docs: http://localhost:8000/docs

### Option B — run the two services by hand

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # creates the DB, plans, and a demo provider + admin
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

### Demo logins (created by `app.seed`)

| Role | Email | Password |
|------|-------|----------|
| Service provider | `demo@leadpilot.io` | `demo1234` |
| Admin | `admin@leadpilot.io` | `admin1234` |

---

## How the AI works

Set `ANTHROPIC_API_KEY` in `.env` to use real Claude models. **Without a key the
app still runs** — the AI layer falls back to deterministic, keyword-based stubs
so you can develop and demo offline. Three AI jobs:

1. **Field matching** (`ai/matcher.py`) — given a discovered post and the
   client's trade + service categories, decide whether it's a genuine lead for
   *this* provider, with a relevance score and reason.
2. **Reply drafting** (`ai/drafter.py`) — write a natural, human-sounding reply
   that merges the client's services, price ranges, and phone number.
3. **Support chatbot** (`ai/support.py`) — answer onboarding and billing
   questions, and escalate to a human admin when needed.

---

## Project layout

```
backend/    FastAPI service (auth, billing, leads, AI, admin)
frontend/   Next.js dashboard, onboarding wizard, admin console
docs/       Architecture and compliance notes
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and
[`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) for the integration guardrails.
