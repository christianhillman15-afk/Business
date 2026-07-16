# Nextdoor Integration

Nextdoor is the primary lead channel, and it works differently from Facebook
under the hood. This doc explains what's possible, what isn't, and how LeadPilot
handles it.

## What Nextdoor's API actually allows

Nextdoor has an official developer platform ([developer.nextdoor.com](https://developer.nextdoor.com)),
**partner-access-gated** ("Apply for access"). Three product families:

| API family | What it does | Use in LeadPilot |
|------------|--------------|------------------|
| **Display / Search** | Find recent **public** posts mentioning your keywords in an area | Lead **discovery** ✅ automatable |
| **Share Content / Create Post** | Publish a **new** post from a neighbor or business profile (`body_text`, media, geo) | **Business Posts** (broadcast) ✅ automatable |
| **Ads** | Create/manage ad campaigns, Local Deals, conversions | Paid reach (future) |

**There is no API to reply or comment on another member's post.** The Create
Post endpoint only makes *new* posts on a feed — confirmed in both the platform
overview and the endpoint reference. And Nextdoor's Member Agreement prohibits
bots/automation, using member credentials, and scraping (crawlers, plugins,
scripts).

**Conclusion:** an AI agent **cannot** autonomously reply on neighbors' Nextdoor
posts without automating a member's logged-in session — which violates the terms
and gets accounts banned. So we don't.

## How LeadPilot handles Nextdoor

Two complementary, compliant paths — both keep your clients' accounts safe.

### 1. Reply-assist (human-in-the-loop) — for individual leads
`backend/app/connectors/nextdoor.py` → `discover()` uses the official Search API
(when live + an approved partner token is set), else the offline sample source.

For each matched lead, the AI drafts a reply. Because there's no reply API, the
**client posts it themselves**: the dashboard shows **Copy reply**, **Open post
↗**, and **I posted it**. The last one records it (for quota + history) without
ever touching the client's account.

- Capability flag: `nextdoor.reply_autopost = False` (see `provider_capabilities`).
- API: `POST /api/responses/{id}/approve` is **blocked** for Nextdoor (409);
  `POST /api/responses/{id}/mark-posted` is the manual confirmation.

### 2. Business Posts (broadcast) — the AI *does* post
`connectors/nextdoor.py` → `broadcast()` publishes a **new** Business Post via
the official Create Post API (when live + token), else simulated.

The AI composes the post (`ai/broadcaster.py`); the client reviews and hits
**Publish**. This is the closest thing to "the agent posts on Nextdoor" that is
fully compliant and automatable.

- Capability flag: `nextdoor.broadcast = True`.
- API: `POST /api/broadcast/draft`, `PUT /api/broadcast/{id}`,
  `POST /api/broadcast/{id}/publish`. UI: the **Business Posts** tab.

## Going live on Nextdoor

1. Apply for Nextdoor API access at [developer.nextdoor.com](https://developer.nextdoor.com)
   (Display/Search + Share Content/Create Post; Ads if you want paid reach).
2. Once approved, capture the partner OAuth token per connected client and store
   it (encrypted automatically). Fill in the exact granted endpoints/params in
   `connectors/nextdoor.py` (the Search + Create Post calls are structured but
   use placeholder paths until your partner scope is confirmed).
3. Set `LEADPILOT_LIVE_CONNECTORS=true`.

Until then, everything runs against the offline sample source and nothing posts
to a real account.

## Sources
- [Nextdoor for Developers](https://developer.nextdoor.com/) — API products & "Apply for access"
- [Create Post reference](https://developer.nextdoor.com/reference/create-post) — new posts (neighbor/business), not comments
- [Nextdoor Ads API launch](https://about.nextdoor.com/press-releases/nextdoor-launches-ads-api-program-offering-advertisers-an-easier-way-to-extend-their-campaigns-to-nextdoor)
- [Promoting a business on Nextdoor](https://help.nextdoor.com/s/article/Promoting-a-business-or-service-on-Nextdoor) — Business Posts, Local Deals
- Nextdoor Member Agreement — prohibitions on bots, automated access, member-credential use, and scraping
