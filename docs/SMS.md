# SMS — leads and a two-way bot

LeadPilot is SMS-first: customers can run everything from their phone.

## What gets texted

When the bot finds a post in the customer's trade it sends **two** texts:

1. The lead — a short summary of the post **and the link** to open it.
2. The **suggested reply** on its own, so it's a clean one-tap copy/paste.

This is gated on the customer's `phone` being set and the **"Text me new
leads"** toggle (Settings) being on. See `run_discovery()` in
`backend/app/services.py`.

## Two-way bot (text your assistant)

Customers can text their LeadPilot number any question — "what's my plan?",
"how many leads today?", "how do I connect Nextdoor?" — and the **same**
assistant that powers the in-app chat texts back. It's knowledge-grounded
(`backend/app/ai/knowledge.py`) and escalates billing/refund/human requests to
the team.

### Wiring Twilio (inbound)

The inbound webhook is `POST /api/sms/inbound` and replies with TwiML, so it
works even before outbound Twilio credentials are set.

1. Buy/choose a Twilio number.
2. In the Twilio console → Phone Numbers → your number → **Messaging** →
   "A message comes in" → Webhook →
   `https://<your-backend-domain>/api/sms/inbound` (HTTP POST).
3. To also send proactive lead texts, set the outbound credentials:
   ```
   SMS_BACKEND=twilio
   TWILIO_ACCOUNT_SID=...
   TWILIO_AUTH_TOKEN=...
   TWILIO_FROM_NUMBER=+1...
   ```

The customer's number is matched to their account by the last 10 digits, so
formatting (spaces, `+1`, parentheses) doesn't matter. Unknown numbers get a
friendly "link this number in Settings" reply.

> Production hardening: validate Twilio's `X-Twilio-Signature` header on the
> inbound route before trusting the request.

## Offline / no provider

With `SMS_BACKEND=console` (default) outbound texts are logged, and the inbound
webhook still returns the assistant's reply as TwiML — so the whole flow is
testable without a Twilio account.
