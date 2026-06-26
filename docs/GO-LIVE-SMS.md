# Go live with texting — step by step

This turns on real two-way SMS: customers get leads and updates by text and can
text the bot back. Plan on ~30–45 min of clicking, plus a 1–3 day wait for
carrier registration (step 4). You do the account steps; the app is already
wired for all of it.

## 0. What you'll create
- A **Render** account (hosts the backend the texts run through) — free tier ok.
- A **Twilio** account + one phone number (the texting line).
- An **Anthropic** API key (optional but recommended, so replies are smart).

---

## 1. Deploy the backend (Render)
1. Go to <https://dashboard.render.com> → **New → Blueprint**.
2. Connect this GitHub repo and pick the branch. Render reads `render.yaml`.
3. Click **Apply**. It creates the database + backend (+ frontend) services.
4. When the backend finishes, copy its URL, e.g.
   `https://leadpilot-backend.onrender.com`.

## 2. Set the backend's settings (Render → leadpilot-backend → Environment)
Fill the values marked "set later":
- `OAUTH_REDIRECT_BASE` = the backend URL from step 1.
- `FRONTEND_BASE_URL` = your demo/frontend URL (used in the `LEADS` text link).
- `CORS_ORIGINS` = your frontend URL.
- `ANTHROPIC_API_KEY` = your key from <https://console.anthropic.com> (optional;
  without it the bot still answers from built-in knowledge).
Click **Save** (it redeploys).

## 3. Get a Twilio number
1. Sign up at <https://www.twilio.com/try-twilio> and verify your email/phone.
2. Console → **Phone Numbers → Buy a number** → pick one with **SMS** enabled
   (~$1–2/mo). In the US, get a **local** or **toll-free** number.
3. Console home shows your **Account SID** and **Auth Token** — keep them handy.

## 4. Register for US business texting (A2P 10DLC) — start this early
US carriers require registering before they'll reliably deliver app texts.
1. Twilio Console → **Messaging → Regulatory Compliance → A2P 10DLC** (or
   "Trust Hub").
2. Register your **Brand** (your business name, EIN/owner info) and a
   **Campaign** (use-case: "Customer Care / account notifications").
3. Submit. Approval is usually **1–3 days**. (Toll-free verification is a similar
   one-time step.) You can finish steps 5–6 now and just wait on delivery.

## 5. Turn texting on (Render → leadpilot-backend → Environment)
- `SMS_BACKEND` = `twilio`
- `TWILIO_ACCOUNT_SID` = from step 3
- `TWILIO_AUTH_TOKEN` = from step 3
- `TWILIO_FROM_NUMBER` = your Twilio number in `+1...` form (e.g. `+15551234567`)
Save (redeploys).

## 6. Point the number at the bot (Twilio)
1. Console → **Phone Numbers → your number → Configure**.
2. Under **Messaging → "A message comes in"**: set **Webhook**,
   `https://<your-backend>/api/sms/inbound`, method **HTTP POST**. Save.

## 7. Test it
1. In your LeadPilot dashboard → **Settings**, set your phone number and keep
   **"Text me new leads"** on.
2. From your phone, text your Twilio number `STATUS` — you should get your plan
   back. Try `HELP`, `LEADS`, and a real question like "how do I connect
   Nextdoor?"
3. On the dashboard, **Scan for leads** → you should receive the two lead texts.

That's it — every lead and update now arrives by text, and the customer can run
everything from their phone.

> Security note for production: validate Twilio's `X-Twilio-Signature` on
> `/api/sms/inbound` so only Twilio can post to it.
