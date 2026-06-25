# Compliance & Integration Guardrails

Read this before building real Facebook / Nextdoor connectors. The platform's
durability depends on getting this right — the fastest way to kill the business
is to get your customers' accounts banned in week one.

## The core principle

**Build the version of this product that survives.** That means:

- **Human-in-the-loop posting.** AI *drafts*; the client *approves* before
  anything is published. This is how the scaffold works today
  (`/api/responses/{id}/approve`). It keeps you defensible and keeps accounts
  safe. Avoid fully-automated covert posting.
- **Official APIs where they exist.** Use the **Meta Graph API** for Facebook
  rather than scraping or driving a logged-in browser session. Official APIs are
  rate-limited and permissioned, but they don't get accounts banned.
- **Opt-in outreach.** Any recruiting / cold-outreach feature should target
  people who have opted in, and must comply with CAN-SPAM, TCPA, and each
  platform's messaging policies. Mass automated cold DMs are spam.

## Things in the original spec to be careful with

| Spec item | Risk | Safer approach |
|-----------|------|----------------|
| Scraping Facebook Groups / Nextdoor | Violates ToS; account bans | Meta Graph API; for Nextdoor use the official Search/Create-Post APIs — see [`NEXTDOOR.md`](NEXTDOOR.md) |
| Storing & automating users' session cookies | ToS violation; account takeover pattern | OAuth tokens with least-privilege scopes; never drive a human's logged-in session covertly |
| "Bypassing city restrictions" + randomized pacing to dodge detection | Detection evasion | Don't build ban-evasion. Operate within platform rules |
| Automated mass cold outreach | CAN-SPAM / platform spam policies | Opt-in only; rate-limited; clear identification + opt-out |

## Connecting accounts (no passwords, no fake accounts)

Clients connect via one of three methods (`backend/app/routers/accounts.py`):

- **OAuth (recommended)** — the client authorizes LeadPilot through the
  platform's official flow. We store the returned token (AES-256 encrypted),
  **never a password.**
- **Managed Business Page** — for clients who don't want to connect anything
  personal, LeadPilot provisions and operates a dedicated **Business Page** for
  their business (a real business identity they own). No credentials change
  hands; the account sits in `provisioning` until the team activates it.
- **Session token (advanced, discouraged)** — a captured token, encrypted at
  rest. Avoid for personal accounts.

**We never fabricate fake personal or "neighbor" accounts.** Platforms verify
real identity/address; fabricated accounts are astroturfing — they get banned
and create legal exposure. The managed **Business Page** is the legitimate way
to give a client a presence without them sharing a login.

## How the architecture keeps you flexible

Connectors implement a single interface (`connectors/base.py`):

```python
class Connector(ABC):
    def discover(self, *, neighborhoods, limit) -> list[CandidatePost]: ...
    def publish(self, *, post_url, reply_text) -> bool: ...
```

The app only ever talks to this interface and a registry
(`connectors/__init__.py`). Today it's wired to `SampleConnector` (a compliant,
offline data source). To integrate a real platform, implement a new connector
against the same interface and swap it in the registry — nothing else in the app
changes. That lets you choose the compliant integration path per platform
without re-plumbing the product.

## Data protection (from the spec, still your responsibility)

- Encrypt any stored credentials/sessions at rest (**AES-256**); the scaffold
  stores only an opaque marker.
- TLS in transit; least-privilege OAuth scopes.
- Audit-log posting actions and auth/credential events (`AuditLog` exists).
- Honor data-deletion and consent requirements (GDPR/CCPA) for anyone whose
  posts or contact info you store.

## Bottom line

You can build ~80% of this product — the dashboard, billing, the lead/CRM model,
AI field-matching and drafting, the support bot, the admin console — with zero
compliance risk, and that's exactly what this repository implements. The
remaining 20% (the live platform integrations) is where judgment is required;
default to official APIs and human-approved actions.
