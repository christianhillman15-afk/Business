# Going Live

This is the path from "runs on my laptop" to "runs on the internet." There are
three things you need that aren't code — get the slow one (Meta) started first.

## The three gates

| Gate | What it is | How long | Cost |
|------|-----------|----------|------|
| **Hosting** | A server on the internet to run the app + a database | ~1 hour | Free tier to start |
| **Stripe account** | To actually charge customers | ~30 min | Free; takes a % of payments |
| **Meta app review** | Facebook's approval to read feeds / post on a user's behalf | **weeks** | Free, but slow — start now |

You can deploy and demo **today** without Stripe or Meta — the app runs with
offline AI + mock billing, and live posting stays off. Add the others as they
come through.

---

## 1. Deploy (Render, free tier)

The repo includes [`render.yaml`](../render.yaml), a blueprint that provisions a
Postgres database, the backend API, and the frontend together.

1. Push this repo to GitHub (already done if you're reading this in a PR).
2. Go to [render.com](https://render.com) → **New → Blueprint** → pick this repo.
3. Render reads `render.yaml` and creates three things: `leadpilot-db`,
   `leadpilot-backend`, `leadpilot-frontend`.
4. After the first deploy, fill in the values it asked you to set:
   - On **leadpilot-frontend** → `NEXT_PUBLIC_API_BASE_URL` = your backend's URL
     (e.g. `https://leadpilot-backend.onrender.com`), then **redeploy** it
     (this URL is baked in at build time).
   - On **leadpilot-backend** → `CORS_ORIGINS` and `FRONTEND_BASE_URL` = your
     frontend's URL (e.g. `https://leadpilot-frontend.onrender.com`).
5. Open the frontend URL and log in with the seeded demo accounts.

`SECRET_KEY` and `ENCRYPTION_KEY` are generated automatically. `DATABASE_URL` is
wired to the Postgres instance for you.

> Other hosts work the same way — anything that runs the two Dockerfiles plus a
> Postgres database (Railway, Fly.io, Heroku, a VPS). The only host-specific
> piece is the blueprint file.

## 2. Turn on real AI

Set `ANTHROPIC_API_KEY` on the backend service (get a key at
[console.anthropic.com](https://console.anthropic.com)). Without it the app uses
the offline stubs; with it, field-matching, drafting, and support use real
Claude models. That's the only change needed.

## 3. Turn on real payments (Stripe)

1. Create a [Stripe](https://stripe.com) account.
2. Set `STRIPE_SECRET_KEY` on the backend. Plan selection now creates a real
   Stripe Checkout and the dashboard redirects to it.
3. Add a webhook in Stripe → endpoint `https://<backend>/api/subscription/webhook`,
   event `checkout.session.completed`. Put its signing secret in
   `STRIPE_WEBHOOK_SECRET`. This is what flips a subscription to "active" after
   payment.
4. (Optional) Pre-create Stripe Prices and map them via `STRIPE_PRICES`
   (`starter:price_…,growth:price_…`). Otherwise the app builds ad-hoc prices.

## 4. Turn on live Facebook (the slow one)

**Do not enable this until your Meta app is approved** — see
[`COMPLIANCE.md`](COMPLIANCE.md).

1. Create an app at [developers.facebook.com](https://developers.facebook.com).
2. Request the permissions you need (Group/Page read + publish) and submit for
   **App Review** with a screencast showing the human-approval flow. This is
   what takes weeks.
3. Once approved, in your connect flow capture the user's OAuth access token and
   store it (the app encrypts it with AES-256 automatically).
4. Set on the backend: `LEADPILOT_LIVE_CONNECTORS=true` and `META_GROUP_IDS` =
   the group/page IDs to watch.

Until then, leave `LEADPILOT_LIVE_CONNECTORS=false` — discovery uses the sample
source and nothing posts to a real account.

## 5. Scheduled scanning (optional)

Set `LEADPILOT_SCHEDULER_ENABLED=true` to scan automatically every
`LEADPILOT_SCHEDULER_INTERVAL_MINUTES`. Or run it as a separate cron job:
`python -m app.tasks discover-all`.

---

## Production checklist

- [ ] `SECRET_KEY` and `ENCRYPTION_KEY` are strong + unique (Render generates these)
- [ ] `DATABASE_URL` points at Postgres, not SQLite
- [ ] `CORS_ORIGINS` / `FRONTEND_BASE_URL` set to your real frontend URL
- [ ] Stripe webhook configured and tested
- [ ] `LEADPILOT_LIVE_CONNECTORS=false` until Meta approves your app
- [ ] CI is green (the `.github/workflows/ci.yml` pipeline runs tests on every push)
- [ ] Add Alembic migrations before you have real customer data to protect
