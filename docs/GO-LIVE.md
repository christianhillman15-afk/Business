# LeadPilot — Go-Live Checklist

Work top to bottom. The whole **app is already built** — every item here is
real-world setup (accounts, keys, approvals), not code.

> ⏱️ **Start these two on Day 1 — they're the slow ones:**
> - **Register your business entity** (Phase 1) — unblocks every form below.
> - **Apply for Nextdoor + Meta API access** (Phase 6) — approval takes weeks.
>
> You can deploy and demo the app (Phases 2–3) the same day, with mock billing
> and offline AI, while those approvals are pending.

---

## Phase 1 — Business foundation
- [ ] Register a business entity (LLC or DBA). Gives you the **legal name +
      address** every form below needs. (~$50–300; a few days)
- [ ] Open a business bank account.
- [ ] Buy a domain (e.g. leadpilot.app). (~$12/yr)
- [ ] Create role inboxes: `support@`, `privacy@`, `no-reply@` on your domain.

## Phase 2 — Deploy (get it online)
- [ ] Merge the pull request to `main` (or deploy from the branch).
- [ ] On [render.com](https://render.com): **New → Blueprint → this repo**. It
      provisions the database, backend, and frontend from `render.yaml`.
- [ ] Set **frontend** `NEXT_PUBLIC_API_BASE_URL` = your backend URL, then
      redeploy the frontend (this value is baked in at build time).
- [ ] Set **backend** `CORS_ORIGINS`, `FRONTEND_BASE_URL`, and
      `OAUTH_REDIRECT_BASE` = your frontend / backend URLs.
- [ ] Point your domain at the frontend (Render → Custom Domain).
- [ ] Confirm `SECRET_KEY` and `ENCRYPTION_KEY` are set to strong values
      (Render generates these automatically).
- [ ] **Security:** change the seeded admin password (`admin@leadpilot.io` /
      `admin1234`) immediately, and remove the demo `demo@leadpilot.io` account
      before real customers sign up.
- [ ] Load the site, sign in, click around. ✅ You now have a live demo URL.

## Phase 3 — Turn on real AI
- [ ] Get an API key at [console.anthropic.com](https://console.anthropic.com).
- [ ] Set backend `ANTHROPIC_API_KEY`. (Drafts/matching/support now use real
      Claude instead of the offline fallback.)

## Phase 4 — Payments (Stripe)
- [ ] Create a [Stripe](https://stripe.com) account; finish business verification.
- [ ] Set backend `STRIPE_SECRET_KEY`.
- [ ] Add a Stripe webhook → `https://<backend>/api/subscription/webhook`, event
      `checkout.session.completed`; set `STRIPE_WEBHOOK_SECRET`.
- [ ] (Optional) Pre-create Prices in Stripe and map them via `STRIPE_PRICES`
      (`solo:price_…,starter:price_…,…`).
- [ ] Test: pick a plan → complete Stripe Checkout → subscription flips to active.

## Phase 5 — Email (transactional)
- [ ] Create an email provider account (Mailgun / Amazon SES / Postmark).
- [ ] Add the SPF/DKIM DNS records they give you (so mail isn't spam-filtered).
- [ ] Set backend `EMAIL_BACKEND=smtp`, `EMAIL_FROM`, and `SMTP_HOST/PORT/USER/
      PASSWORD/USE_TLS`.
- [ ] Test: start a trial → confirm the welcome + magic-link email arrives.

## Phase 6 — Platform API access (start early — weeks)
**Nextdoor** ([developer.nextdoor.com](https://developer.nextdoor.com))
- [ ] Apply for API access: **Display** (Search — finds leads) + **Share
      Content** (Create Post — Business Posts). Add **Ads** if you want paid
      Local Deals.
- [ ] On approval, set `NEXTDOOR_CLIENT_ID` / `NEXTDOOR_CLIENT_SECRET`, and fill
      in the exact granted endpoints in `backend/app/connectors/nextdoor.py`.

**Meta / Facebook** ([developers.facebook.com](https://developers.facebook.com))
- [ ] Create an app; request Pages permissions; submit for **App Review** with a
      screencast of the human-approval flow.
- [ ] On approval, set `META_CLIENT_ID` / `META_CLIENT_SECRET` and `META_GROUP_IDS`.

**Flip it live (only after the above is approved):**
- [ ] Set `LEADPILOT_LIVE_CONNECTORS=true`.
- [ ] Set `LEADPILOT_SCHEDULER_ENABLED=true` to auto-scan + auto-publish on a
      schedule.

## Phase 7 — Legal & compliance
- [ ] Have a lawyer review/replace the templated `/terms` and `/privacy` pages.
- [ ] Confirm your outreach is compliant: official Nextdoor/Meta APIs only,
      human-approved posting, opt-in for any email/SMS (CAN-SPAM/TCPA). See
      `docs/COMPLIANCE.md`. **No fake accounts, no bot DMs, no ban evasion** —
      these get accounts banned and create legal exposure.

## Phase 8 — Pilot & launch
- [ ] Create your real admin account; remove demo data.
- [ ] Onboard **one real service business** end-to-end as a pilot.
- [ ] Watch logs + CI; confirm billing, email, and (if live) posting all work.
- [ ] Launch. 🚀

---

### Quick env-var reference
All of these are in `.env.example`. On Render, set them on the **backend**
service (except `NEXT_PUBLIC_API_BASE_URL`, which is on the **frontend**).

| Phase | Variables |
|------|-----------|
| Deploy | `NEXT_PUBLIC_API_BASE_URL`, `CORS_ORIGINS`, `FRONTEND_BASE_URL`, `OAUTH_REDIRECT_BASE`, `SECRET_KEY`, `ENCRYPTION_KEY` |
| AI | `ANTHROPIC_API_KEY` |
| Payments | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICES` |
| Email | `EMAIL_BACKEND`, `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS` |
| Connectors | `META_CLIENT_ID`, `META_CLIENT_SECRET`, `META_GROUP_IDS`, `NEXTDOOR_CLIENT_ID`, `NEXTDOOR_CLIENT_SECRET`, `LEADPILOT_LIVE_CONNECTORS`, `LEADPILOT_SCHEDULER_ENABLED` |
