"""Single source of truth about how LeadPilot works.

Used by the support assistant (in-app chat AND two-way SMS) so it answers with
real product knowledge, and as a reference for tone. Keep it plain-language —
the audience is busy local tradespeople, not engineers.
"""
from __future__ import annotations

from ..plans import PLANS


def plans_blurb() -> str:
    return "; ".join(
        f"{p.name} ${p.price_monthly}/mo (up to {p.daily_post_quota} "
        f"{'reply' if p.daily_post_quota == 1 else 'replies'}/day)"
        for p in PLANS.values()
    )


# Curated questions shown as one-tap chips in the chat and offered over SMS.
SUGGESTED_QUESTIONS: list[str] = [
    "How does LeadPilot find me leads?",
    "How do I get leads by text?",
    "What does it cost?",
    "How do I connect Nextdoor?",
    "Why am I not getting leads yet?",
    "Can I edit a reply before it posts?",
    "How do I talk to my bot by text?",
    "How do I cancel or change plans?",
]


def knowledge_base() -> str:
    return f"""
ABOUT LEADPILOT
LeadPilot is an AI assistant for local service businesses (plumbers, cleaners,
landscapers, painters, handymen, and similar). It watches local Nextdoor and
Facebook groups, finds neighbors asking for the kind of work you do, and writes
a ready-to-send reply that includes your services, pricing, and phone number.
You stay in control — you approve before anything is posted.

ONLY YOUR TRADE (FIELD MATCHING)
Every post is scored against your trade and service categories. A plumber only
gets plumbing jobs; a landscaper only gets landscaping jobs. Off-trade posts
(e.g. someone asking a plumber for a house cleaner) are filtered out so you
never waste time or a reply on the wrong lead.

GETTING LEADS BY TEXT (SMS-FIRST)
The easiest way to use LeadPilot is by text. When the bot finds a matching post
it sends you TWO texts:
  1) A text with the post (a short summary + the link to open it).
  2) A separate text with the suggested reply, by itself, so you can copy and
     paste it in one tap.
Keep "Text me new leads" on in Settings and make sure your phone number is
correct. Standard message rates may apply.

TALK TO YOUR BOT BY TEXT
You can text your LeadPilot number any question, any time — "what's my plan?",
"how many leads today?", "how do I connect Facebook?" — and the assistant texts
you back. It's the same assistant as this in-app chat, just over SMS, so you
never have to log in if you don't want to.

NEXTDOOR vs FACEBOOK
- Nextdoor: replying to someone else's post has no public API, so LeadPilot
  drafts the reply and you post it with one tap (Copy reply / Open post on the
  dashboard, or straight from the text it sends you). LeadPilot can also publish
  your own "Business Posts" through Nextdoor's official API on a schedule.
- Facebook: LeadPilot can post the approved reply for you automatically through
  the official Graph API once your Page/Group is connected.

CONNECTING ACCOUNTS (NO PASSWORD SHARING)
Go to Setup. Connect with the platform's official authorize button — LeadPilot
never asks for or stores your password — or choose "Set up a Business Page for
me" and we provision a dedicated page for your business. A green badge means
you're connected.

APPROVALS & SAFETY
Nothing posts without your say-so. You can edit any reply first, approve it, or
decline it. Daily limits (your plan's cap) keep your accounts safe and natural.

PRICING & PLANS
Plans are billed monthly by your daily reply limit — an "up to" cap, not a
guarantee, since some days have fewer in-field leads. Tiers: {plans_blurb()}.
Change plans anytime under Billing. There's a 7-day free trial with 1 reply/day
and no card required; sign-in is a one-click email link (no password).

BILLING / CANCELING
You can switch or cancel your plan anytime from the Billing tab. For refunds,
double charges, or disputes, the assistant loops in a human on the team.

TROUBLESHOOTING
- "Not getting leads": check that your Trade and Service categories are filled
  in under Setup, your target neighborhoods are set, an account is connected,
  and you have daily quota left. Click "Scan for leads" to run it now.
- "The reply doesn't sound right": tap Edit on the lead to tweak it before it
  posts; the AI learns from your pricing and services in Setup.
- "Not getting texts": confirm your phone number in Settings and that "Text me
  new leads" is on.
""".strip()
