"use client";

// In-browser demo backend. When NEXT_PUBLIC_DEMO_MODE=true the app ships as a
// fully static site (GitHub Pages) with no real API — every request below is
// served from this in-memory store so the whole product is clickable. Actions
// (approve, scan, draft, etc.) mutate the store so they feel real within a
// session; a reload resets to the seeded state.
//
// This file has ZERO runtime dependency on the backend. Types are imported with
// `import type` only, so there is no import cycle with ./api.
import type {
  Broadcast,
  Capabilities,
  ClientDetail,
  ClientSummary,
  ConnectedAccount,
  Lead,
  Notification as Notif,
  Plan,
  PricingProfile,
  Quota,
  Subscription,
  User,
} from "./api";

export const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

const DEMO_TOKEN = "demo-token";
export const ADMIN_TOKEN = "demo-admin-token";
export function isDemoToken(t: string | null) {
  return t === DEMO_TOKEN || t === ADMIN_TOKEN;
}

function isAdmin(): boolean {
  try {
    return window.localStorage.getItem("leadpilot_token") === ADMIN_TOKEN;
  } catch {
    return false;
  }
}

const ago = (mins: number) => new Date(Date.now() - mins * 60000).toISOString();

const PLANS: Plan[] = [
  { code: "solo", name: "Solo", price_monthly: 200, daily_post_quota: 1 },
  { code: "starter", name: "Starter", price_monthly: 250, daily_post_quota: 2 },
  { code: "growth", name: "Growth", price_monthly: 300, daily_post_quota: 4 },
  { code: "pro", name: "Pro", price_monthly: 350, daily_post_quota: 6 },
  { code: "scale", name: "Scale", price_monthly: 400, daily_post_quota: 8 },
];

const SUPPORT_SUGGESTIONS = [
  "How does LeadPilot find me leads?",
  "How do I get leads by text?",
  "What does it cost?",
  "How do I connect Nextdoor?",
  "Why am I not getting leads yet?",
  "Can I edit a reply before it posts?",
  "How do I talk to my bot by text?",
  "How do I cancel or change plans?",
];

function plansBlurb() {
  return PLANS.map(
    (p) =>
      `${p.name} $${p.price_monthly}/mo (up to ${p.daily_post_quota}/day)`,
  ).join("; ");
}

function makeResponse(id: number, text: string) {
  return { id, generated_text: text, status: "draft" as const, posted_at: null };
}

// --- seeded, mutable store --------------------------------------------------
const s: {
  user: User;
  quota: Quota;
  caps: Capabilities;
  leads: Lead[];
  broadcasts: Broadcast[];
  notifications: Notif[];
  accounts: ConnectedAccount[];
  subscription: Subscription;
  profile: PricingProfile;
  nextId: number;
} = {
  user: {
    id: 1,
    email: "demo@leadpilot.io",
    role: "provider",
    business_name: "Rivertown Plumbing Co.",
    contact_name: "Jordan Rivers",
    phone: "(555) 014-7788",
    nextdoor_handle: "rivertown-plumbing",
    onboarding_source: "demo",
    timezone: "America/New_York",
    automation_enabled: false,
    sms_enabled: true,
  },
  quota: {
    plan_code: "growth",
    daily_quota: 4,
    used_today: 1,
    remaining_today: 3,
    on_trial: false,
  },
  caps: {
    facebook: { reply_autopost: true, broadcast: true },
    nextdoor: { reply_autopost: false, broadcast: true },
  },
  leads: [
    {
      id: 101,
      provider: "nextdoor",
      post_url: "https://nextdoor.com/p/demo-water-heater",
      author: "Dana M.",
      content:
        "Our water heater died this morning — anyone know a good plumber who can come today?? 😩",
      location: "Maple Heights",
      status: "drafted",
      relevance_score: 0.94,
      relevance_reason: "Water heater failure — core plumbing service.",
      created_at: ago(28),
      response: makeResponse(
        201,
        "Hi! I'm with Rivertown Plumbing Co. — we do same-day water heater repair & replacement. Service call is $89 and installs start at $1,200. Call or text us at (555) 014-7788 and we'll get your hot water back today. 🔧",
      ),
    },
    {
      id: 102,
      provider: "facebook",
      post_url: "https://facebook.com/groups/demo/posts/leak",
      author: "Chris P.",
      content:
        "Kitchen sink is leaking under the cabinet and I'm getting water damage. Need someone ASAP — recommendations?",
      location: "Rivertown",
      status: "drafted",
      relevance_score: 0.88,
      relevance_reason: "Under-sink leak — matches leak repair.",
      created_at: ago(96),
      response: makeResponse(
        202,
        "So sorry about the leak! Rivertown Plumbing can stop the water damage fast — we handle under-sink leaks every day. Service call is $89 and most leak repairs start at $150. Text or call (555) 014-7788 and we'll come right out.",
      ),
    },
    {
      id: 103,
      provider: "nextdoor",
      post_url: "https://nextdoor.com/p/demo-toilet",
      author: "Priya R.",
      content:
        "Looking for a reliable plumber to replace an old toilet and fix a running one. Who do you all use?",
      location: "Oakwood",
      status: "drafted",
      relevance_score: 0.81,
      relevance_reason: "Toilet replacement & repair — in trade.",
      created_at: ago(180),
      response: makeResponse(
        203,
        "Happy to help! Rivertown Plumbing replaces and repairs toilets all the time. A standard swap runs about $250 plus the fixture, and fixing a runner is usually a quick $89 service call. Reach us at (555) 014-7788 and we'll get it sorted.",
      ),
    },
    {
      id: 110,
      provider: "nextdoor",
      post_url: null,
      author: "Sam T.",
      content: "Can anyone recommend a good landscaper for weekly lawn care?",
      location: "Maple Heights",
      status: "filtered",
      relevance_score: 0.11,
      relevance_reason: "Landscaping — outside your trade (plumbing).",
      created_at: ago(140),
      response: null,
    },
    {
      id: 111,
      provider: "facebook",
      post_url: null,
      author: "Alex W.",
      content: "Looking for a house cleaner every two weeks, any recommendations?",
      location: "Rivertown",
      status: "filtered",
      relevance_score: 0.07,
      relevance_reason: "Home cleaning — not a plumbing service.",
      created_at: ago(220),
      response: null,
    },
    {
      id: 112,
      provider: "nextdoor",
      post_url: null,
      author: "Jordan K.",
      content: "Need an electrician to install a ceiling fan this weekend.",
      location: "Oakwood",
      status: "filtered",
      relevance_score: 0.19,
      relevance_reason: "Electrical — adjacent but outside plumbing.",
      created_at: ago(300),
      response: null,
    },
  ],
  broadcasts: [
    {
      id: 301,
      provider: "nextdoor",
      body_text:
        "👋 Neighbors! Rivertown Plumbing here. Slow drains or a dripping faucet before the holidays? We do same-day service across Rivertown, Maple Heights & Oakwood. Service calls $89, no surprise fees. Call/text (555) 014-7788.",
      status: "draft",
      scheduled_for: null,
      posted_at: null,
      created_at: ago(55),
    },
    {
      id: 302,
      provider: "facebook",
      body_text:
        "🚿 Spring plumbing tune-up season is here. Ask us about a whole-home check: water heater, shutoff valves, and a leak scan. Mention this post for $25 off. — Rivertown Plumbing, (555) 014-7788.",
      status: "posted",
      scheduled_for: null,
      posted_at: ago(1440),
      created_at: ago(1520),
    },
  ],
  notifications: [
    {
      id: 401,
      kind: "lead",
      title: "New in-field lead on Nextdoor",
      body: "Water heater request in Maple Heights — 94% match. A reply is drafted and waiting.",
      read: false,
      created_at: ago(28),
    },
    {
      id: 402,
      kind: "lead",
      title: "New in-field lead on Facebook",
      body: "Under-sink leak in Rivertown — reply ready to approve & post.",
      read: false,
      created_at: ago(96),
    },
    {
      id: 403,
      kind: "system",
      title: "Welcome to LeadPilot",
      body: "Your AI is now watching local Nextdoor & Facebook feeds for plumbing jobs.",
      read: true,
      created_at: ago(2880),
    },
  ],
  accounts: [
    {
      id: 501,
      provider: "nextdoor",
      auth_method: "managed_business_page",
      display_name: "Rivertown Plumbing Co.",
      health: "healthy",
      connected_at: ago(4320),
    },
  ],
  subscription: { plan_code: "growth", status: "active", trial_end: null },
  profile: {
    trade: "plumbing",
    service_categories: [
      "leak repair",
      "water heaters",
      "drain cleaning",
      "toilet repair",
    ],
    price_list:
      "Service call $89; drain cleaning from $150; water heater install from $1,200; toilet swap ~$250 + fixture.",
    phone: "(555) 014-7788",
    target_neighborhoods: ["Rivertown", "Maple Heights", "Oakwood"],
  },
  nextId: 1000,
};

// --- Admin (CRM) demo data --------------------------------------------------
const adminUser: User = {
  id: 99,
  email: "admin@leadpilot.io",
  role: "admin",
  business_name: "LeadPilot HQ",
  contact_name: "Christian",
  phone: null,
  nextdoor_handle: null,
  onboarding_source: "admin",
  timezone: "America/New_York",
  automation_enabled: true,
  sms_enabled: true,
};

let contactSeq = 9000;

const adminClients: ClientDetail[] = [
  {
    id: 1,
    email: "jordan@rivertownplumbing.com",
    business_name: "Rivertown Plumbing Co.",
    contact_name: "Jordan Rivers",
    phone: "(555) 014-7788",
    city: "Rivertown",
    state: "OH",
    service_radius_miles: 20,
    client_notes:
      "Long-time client, pays on time. Wants more water-heater jobs in winter.",
    bot_notes:
      "Texts back within minutes and is very upbeat about the product — already booked 3 jobs. Prefers short, casual replies and likes when we mention same-day service.",
    claimed_by: "Christian",
    client_status: "enabled",
    trade: "plumbing",
    services: [
      "leak repair",
      "water heater install",
      "drain cleaning",
      "toilet repair",
    ],
    plan_code: "growth",
    trial_active: false,
    trial_days_left: null,
    trial_end: null,
    contacts: [
      { id: 8001, name: "Jordan (owner)", phone: "(555) 014-7788", email: "jordan@rivertownplumbing.com" },
      { id: 8002, name: "Dispatch line", phone: "(555) 014-2200", email: null },
    ],
  },
  {
    id: 2,
    email: "maria@sparkleclean.co",
    business_name: "Sparkle Home Cleaning",
    contact_name: "Maria Lopez",
    phone: "(555) 220-9100",
    city: "Maple Heights",
    state: "OH",
    service_radius_miles: 15,
    client_notes: "Signed up last week. Eager but new to Nextdoor.",
    bot_notes:
      "Replies a few times a day, asks a lot of how-to questions. Friendly but needs hand-holding on connecting accounts.",
    claimed_by: null,
    client_status: "enabled",
    trade: "house cleaning",
    services: ["recurring cleaning", "deep cleaning", "move-out cleaning"],
    plan_code: "starter",
    trial_active: true,
    trial_days_left: 4,
    trial_end: new Date(Date.now() + 4 * 86400000).toISOString(),
    contacts: [
      { id: 8003, name: "Maria", phone: "(555) 220-9100", email: "maria@sparkleclean.co" },
    ],
  },
  {
    id: 3,
    email: "deshawn@greenbladelawn.com",
    business_name: "GreenBlade Lawncare",
    contact_name: "DeShawn Carter",
    phone: "(555) 771-3030",
    city: "Oakwood",
    state: "OH",
    service_radius_miles: 30,
    client_notes: "Seasonal — wants to pause in winter. Follow up in March.",
    bot_notes:
      "Slow to respond (1–2 days) and a bit skeptical of AI. Warmed up after the first booked job. Keep replies plain and no-nonsense.",
    claimed_by: "Alex",
    client_status: "enabled",
    trade: "landscaping",
    services: ["weekly mowing", "leaf cleanup", "mulching", "hedge trimming"],
    plan_code: "growth",
    trial_active: true,
    trial_days_left: 1,
    trial_end: new Date(Date.now() + 1 * 86400000).toISOString(),
    contacts: [
      { id: 8004, name: "DeShawn", phone: "(555) 771-3030", email: "deshawn@greenbladelawn.com" },
    ],
  },
  {
    id: 4,
    email: "tony@trucoatpainting.com",
    business_name: "TruCoat Painters",
    contact_name: "Tony Russo",
    phone: "(555) 660-1212",
    city: "Rivertown",
    state: "OH",
    service_radius_miles: 25,
    client_notes: "Trial expired, hasn't picked a plan. Paused texts for now.",
    bot_notes:
      "Went quiet after the trial. Last texts were positive but said 'need to think about budget.' Good candidate for a call about the Solo plan.",
    claimed_by: null,
    client_status: "disabled",
    trade: "painting",
    services: ["interior painting", "exterior painting", "cabinet refinishing"],
    plan_code: "solo",
    trial_active: false,
    trial_days_left: null,
    trial_end: null,
    contacts: [],
  },
];

function clientSummary(c: ClientDetail): ClientSummary {
  return {
    id: c.id,
    business_name: c.business_name,
    contact_name: c.contact_name,
    city: c.city,
    state: c.state,
    client_status: c.client_status,
    claimed_by: c.claimed_by,
    plan_code: c.plan_code,
    trial_active: c.trial_active,
    trial_days_left: c.trial_days_left,
  };
}

// --- Custom Response Generator demo state -----------------------------------
// The demo showcases the free-trial experience: 3 generations/day, then upgrade.
const GEN_TRIAL_LIMIT = 3;
let genUsedToday = 0;
const genHistory: {
  id: number;
  post_content: string;
  platform: string | null;
  reply: string;
  created_at: string;
}[] = [];

function genUsage() {
  return {
    used_today: genUsedToday,
    daily_limit: GEN_TRIAL_LIMIT,
    remaining: Math.max(0, GEN_TRIAL_LIMIT - genUsedToday),
    unlimited: false,
    on_trial: true,
  };
}

function demoReply(content: string, platform?: string | null): string {
  const biz = s.user.business_name || "our team";
  const phone = s.profile.phone || "us";
  const svc = s.profile.service_categories[0] || "the work you need";
  const price = s.profile.price_list
    ? s.profile.price_list.split(";")[0].trim() + "."
    : "honest, upfront pricing.";
  const lower = (content || "").toLowerCase();
  let opener = "Happy to help!";
  if (/asap|emergency|today|right now|urgent/.test(lower))
    opener = "So sorry you're dealing with this — we can usually get out same day.";
  else if (/quote|price|cost|estimate|how much/.test(lower))
    opener = "Happy to give you a quick quote!";
  else if (/recommend|anyone know|who do you/.test(lower))
    opener = "Glad to help a neighbor!";
  const onPlatform = platform ? "" : "";
  return (
    `Hi! I'm with ${biz}. ${opener} We handle ${svc} and more — ${price} ` +
    `Call or text ${phone} and I'll take care of you.${onPlatform}`
  );
}

// Pool of leads revealed one-at-a-time when the user clicks "Scan for leads".
const DISCOVERY_POOL = [
  {
    author: "Morgan L.",
    location: "Rivertown",
    content:
      "Low water pressure in the whole house all of a sudden — is that a plumber thing? Who's good around here?",
    reason: "Whole-house pressure issue — plumbing diagnostic.",
    score: 0.86,
    reply:
      "Great question — yes, that's right up our alley. Sudden whole-house pressure drops are usually a quick diagnosis. Rivertown Plumbing can take a look today; service call is $89 and we'll tell you exactly what's going on before any work. (555) 014-7788.",
  },
  {
    author: "Taylor B.",
    location: "Oakwood",
    content:
      "Garbage disposal stopped working and now the sink is backing up. Help! Any plumber recs?",
    reason: "Disposal + backup — drain/disposal service.",
    score: 0.83,
    reply:
      "We can help! Disposal jams and the backups they cause are an everyday fix for us. Rivertown Plumbing charges an $89 service call and most disposal repairs are done same visit. Text/call (555) 014-7788 and we'll get your sink draining again.",
  },
  {
    author: "Riley S.",
    location: "Maple Heights",
    content:
      "Running toilet is wasting so much water. Is this an easy fix or do I need a pro?",
    reason: "Running toilet — quick plumbing repair.",
    score: 0.79,
    reply:
      "Usually a quick fix! A running toilet is typically a worn flapper or fill valve — an $89 service call covers it in most cases. Rivertown Plumbing can swing by and stop the waste. Reach us at (555) 014-7788.",
  },
];

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

function notFound(path: string): never {
  throw new Error(`Demo backend has no handler for ${path}`);
}

function route(method: string, path: string, body: any): unknown {
  const m = (re: RegExp) => path.match(re);

  // --- auth ---------------------------------------------------------------
  if (path === "/api/auth/login" && method === "POST")
    return {
      access_token: (body?.email ?? "").toLowerCase().includes("admin")
        ? ADMIN_TOKEN
        : DEMO_TOKEN,
    };
  if (path === "/api/auth/register" && method === "POST")
    return { access_token: DEMO_TOKEN };
  if (path === "/api/auth/start-trial" && method === "POST")
    return { access_token: DEMO_TOKEN };
  if (path === "/api/auth/magic/request" && method === "POST")
    return { ok: true };
  if (path === "/api/auth/magic/verify" && method === "POST")
    return { access_token: DEMO_TOKEN };
  if (path === "/api/auth/me") return isAdmin() ? adminUser : s.user;

  // --- catalog / read models ---------------------------------------------
  if (path === "/api/plans") return PLANS;
  if (path === "/api/capabilities") return s.caps;
  if (path === "/api/leads/quota") return s.quota;
  if (path === "/api/leads") return s.leads;
  if (path === "/api/subscription") return s.subscription;
  if (path === "/api/profile" && method === "GET") return s.profile;
  if (path === "/api/accounts" && method === "GET") return s.accounts;
  if (path === "/api/broadcast" && method === "GET") return s.broadcasts;
  if (path === "/api/notifications" && method === "GET") return s.notifications;
  if (path === "/api/notifications/unread-count")
    return { unread: s.notifications.filter((n) => !n.read).length };

  // --- leads --------------------------------------------------------------
  if (path === "/api/leads/discover" && method === "POST") {
    if (s.quota.remaining_today <= 0) return { found: 0 };
    const t = DISCOVERY_POOL[s.leads.length % DISCOVERY_POOL.length];
    const id = ++s.nextId;
    s.leads.unshift({
      id,
      provider: "nextdoor",
      post_url: "https://nextdoor.com/p/demo-" + id,
      author: t.author,
      content: t.content,
      location: t.location,
      status: "drafted",
      relevance_score: t.score,
      relevance_reason: t.reason,
      created_at: new Date().toISOString(),
      response: makeResponse(++s.nextId, t.reply),
    });
    s.quota.used_today += 1;
    s.quota.remaining_today = Math.max(0, s.quota.remaining_today - 1);
    s.notifications.unshift({
      id: ++s.nextId,
      kind: "lead",
      title: "New in-field lead on Nextdoor",
      body: `${t.reason} ${t.location} — reply drafted.`,
      read: false,
      created_at: new Date().toISOString(),
    });
    return { found: 1 };
  }

  // --- automation ---------------------------------------------------------
  if (path === "/api/automation/toggle" && method === "POST") {
    s.user.automation_enabled = !s.user.automation_enabled;
    return { automation_enabled: s.user.automation_enabled };
  }

  // --- responses ----------------------------------------------------------
  let mm = m(/^\/api\/responses\/(\d+)(?:\/(\w+(?:-\w+)?))?$/);
  if (mm) {
    const rid = Number(mm[1]);
    const action = mm[2];
    const lead = s.leads.find((l) => l.response?.id === rid);
    if (!lead || !lead.response) return { ok: true };
    if (method === "PUT") {
      lead.response.generated_text = body?.generated_text ?? lead.response.generated_text;
      return lead.response;
    }
    if (action === "approve" || action === "mark-posted") {
      lead.response.status = "posted";
      lead.response.posted_at = new Date().toISOString();
      lead.status = "engaged";
      return lead.response;
    }
    if (action === "reject") {
      s.leads = s.leads.filter((l) => l.id !== lead.id);
      return { ok: true };
    }
    return { ok: true };
  }

  // --- account ------------------------------------------------------------
  if (path === "/api/account" && method === "PATCH") {
    const allowed = [
      "business_name",
      "phone",
      "timezone",
      "nextdoor_handle",
      "sms_enabled",
    ] as const;
    for (const k of allowed)
      if (body?.[k] !== undefined) (s.user as any)[k] = body[k];
    return s.user;
  }
  if (path === "/api/account/password" && method === "POST") return { ok: true };
  if (path === "/api/account" && method === "DELETE") return undefined;

  // --- profile ------------------------------------------------------------
  if (path === "/api/profile" && method === "PUT") {
    s.profile = { ...s.profile, ...body };
    return s.profile;
  }

  // --- connected accounts -------------------------------------------------
  mm = m(/^\/api\/accounts\/oauth\/(\w+)\/start$/);
  if (mm) return { authorize_url: "#" };
  if (path === "/api/accounts" && method === "POST") {
    const acc: ConnectedAccount = {
      id: ++s.nextId,
      provider: body.provider,
      auth_method: body.auth_method ?? "managed_business_page",
      display_name: body.display_name ?? s.user.business_name,
      health: "healthy",
      connected_at: new Date().toISOString(),
    };
    s.accounts.push(acc);
    return acc;
  }
  mm = m(/^\/api\/accounts\/(\d+)$/);
  if (mm && method === "DELETE") {
    s.accounts = s.accounts.filter((a) => a.id !== Number(mm![1]));
    return undefined;
  }

  // --- subscription / billing --------------------------------------------
  if (path === "/api/subscription/select" && method === "POST") {
    const plan = PLANS.find((p) => p.code === body.plan_code) ?? PLANS[2];
    s.subscription = { plan_code: plan.code, status: "active", trial_end: null };
    s.quota.plan_code = plan.code;
    s.quota.daily_quota = plan.daily_post_quota;
    s.quota.on_trial = false;
    s.quota.remaining_today = Math.max(
      0,
      plan.daily_post_quota - s.quota.used_today,
    );
    return { subscription: s.subscription, checkout_url: null };
  }

  // --- business posts (broadcast) ----------------------------------------
  if (path === "/api/broadcast/draft" && method === "POST") {
    const provider = body?.provider ?? "nextdoor";
    const topic = body?.topic;
    const post: Broadcast = {
      id: ++s.nextId,
      provider,
      body_text: topic
        ? `👋 Neighbors! ${topic} — Rivertown Plumbing has you covered across Rivertown, Maple Heights & Oakwood. Licensed & insured, $89 service calls, same-day when we can. Call/text (555) 014-7788.`
        : "👋 Neighbors! Rivertown Plumbing here for all things plumbing — leaks, water heaters, drains and more. Honest pricing, $89 service calls, same-day service when available. Call/text (555) 014-7788.",
      status: "draft",
      scheduled_for: null,
      posted_at: null,
      created_at: new Date().toISOString(),
    };
    s.broadcasts.unshift(post);
    return post;
  }
  mm = m(/^\/api\/broadcast\/(\d+)(?:\/(\w+))?$/);
  if (mm) {
    const bid = Number(mm[1]);
    const action = mm[2];
    const post = s.broadcasts.find((b) => b.id === bid);
    if (!post) return { ok: true };
    if (method === "DELETE") {
      s.broadcasts = s.broadcasts.filter((b) => b.id !== bid);
      return undefined;
    }
    if (method === "PUT") {
      post.body_text = body?.body_text ?? post.body_text;
      return post;
    }
    if (action === "publish") {
      post.status = "posted";
      post.posted_at = new Date().toISOString();
      return post;
    }
    if (action === "schedule") {
      post.status = "scheduled";
      post.scheduled_for = body?.scheduled_for ?? null;
      return post;
    }
    return post;
  }

  // --- notifications ------------------------------------------------------
  if (path === "/api/notifications/read-all" && method === "POST") {
    s.notifications.forEach((n) => (n.read = true));
    return { ok: true };
  }
  mm = m(/^\/api\/notifications\/(\d+)\/read$/);
  if (mm && method === "POST") {
    const n = s.notifications.find((x) => x.id === Number(mm![1]));
    if (n) n.read = true;
    return { ok: true };
  }

  // --- custom response generator ------------------------------------------
  if (path === "/api/generate/usage") return genUsage();
  if (path === "/api/generate/history") return genHistory.slice(0, 10);
  if (path === "/api/generate" && method === "POST") {
    if (genUsedToday >= GEN_TRIAL_LIMIT) {
      throw {
        status: 429,
        detail:
          "You've used your 3 free trial generations today. Upgrade for unlimited.",
      };
    }
    const id = ++s.nextId;
    const reply = demoReply(body?.post_content ?? "", body?.platform);
    genUsedToday += 1;
    genHistory.unshift({
      id,
      post_content: body?.post_content ?? "",
      platform: body?.platform ?? null,
      reply,
      created_at: new Date().toISOString(),
    });
    return { id, reply, usage: genUsage() };
  }

  // --- support assistant --------------------------------------------------
  if (path === "/api/support/suggestions")
    return { suggestions: SUPPORT_SUGGESTIONS };
  if (path === "/api/support/chat" && method === "POST") {
    const t: string = (body?.message ?? "").toLowerCase();
    const has = (...w: string[]) => w.some((x) => t.includes(x));
    const escalated =
      /refund|cancel my|charged twice|double charge|speak to (someone|a person)|human|dispute|lawsuit|legal|complaint|banned|suspended/.test(
        t,
      );
    let reply: string;
    if (has("text", "sms", "message") && has("bot", "you", "talk", "ask", "question"))
      reply =
        "You can text me anytime at your LeadPilot number — ask things like “what's my plan?”, “how many leads today?”, or “how do I connect Facebook?” and I'll text right back. Same assistant as this chat, just over SMS, so you never have to log in.";
    else if (has("text", "sms") || (has("lead", "post") && has("notify", "alert", "send")))
      reply =
        "Every time the bot finds a job in your trade, it texts you two messages: one with the post and its link, and a second with the suggested reply by itself so you can copy-paste it in one tap. Keep “Text me new leads” on in Settings and make sure your phone number is right.";
    else if (has("find", "how does", "how do you", "discover", "work"))
      reply =
        "I watch local Nextdoor and Facebook groups for neighbors asking for the kind of work you do, then write a ready-to-send reply with your services, pricing, and phone number. You approve before anything posts — and I text every lead to you. Set your trade under Setup, then tap “Scan for leads.”";
    else if (has("connect", "facebook", "nextdoor", "account", "link"))
      reply =
        "Head to Setup → Connect accounts. Use the official “Connect” button (no password is ever shared with us) or pick “Set up a Business Page for me.” A green badge means you're connected. On Nextdoor I draft replies for you to post in one tap; on Facebook I can post for you automatically.";
    else if (has("price", "plan", "cost", "how much", "billing"))
      reply = `Plans are billed monthly by your daily reply limit (an “up to” cap): ${plansBlurb()}. Every plan starts with a 7-day free trial — 1 reply/day, no card. Change plans anytime under Billing.`;
    else if (has("quota", "limit", "how many", "per day", "daily"))
      reply =
        "Your plan sets how many AI replies can post per day — it's an “up to” cap, since some days have fewer in-field leads. It resets at midnight in your local timezone, and I'll alert you when you're out. You're on Growth: up to 4/day.";
    else if (has("edit", "approve", "decline", "don't post", "change the reply"))
      reply =
        "You're always in control. On each lead you can tap Edit to tweak the wording, Approve & post (or “I posted it” for Nextdoor), or Decline. Nothing goes out without your okay.";
    else if (has("not getting", "no leads", "why am i not", "isn't working", "not working"))
      reply =
        "Let's get you leads. Check that (1) your Trade and Service categories are filled in under Setup, (2) your target neighborhoods are set, (3) an account is connected, and (4) you still have quota today. Then tap “Scan for leads.” Want me to walk through any of these?";
    else if (has("trial", "free"))
      reply =
        "The free trial runs 7 days with 1 AI reply per day — no card needed. Sign-in is a one-click email link, so there's no password to remember. Pick a paid plan whenever you're ready.";
    else
      reply =
        "Happy to help! I can explain how leads work, getting leads by text, pricing, connecting Nextdoor or Facebook, your daily limit, or billing. What would you like to know?";
    if (escalated)
      reply =
        "I've noted this and I'm looping in a teammate who can help — they'll follow up by email shortly. Anything else I can do in the meantime?";
    return { ticket_id: 1, reply, escalated };
  }

  // --- admin: client CRM --------------------------------------------------
  if (path === "/api/admin/clients" && method === "GET")
    return adminClients.map(clientSummary);
  mm = m(/^\/api\/admin\/clients\/(\d+)$/);
  if (mm) {
    const cid = Number(mm[1]);
    const client = adminClients.find((c) => c.id === cid);
    if (!client) return notFound(path);
    if (method === "GET") return client;
    if (method === "PATCH") {
      const { services, trade, ...rest } = body ?? {};
      Object.assign(client, rest);
      if (trade !== undefined) client.trade = trade;
      if (services !== undefined) client.services = services;
      return client;
    }
  }
  mm = m(/^\/api\/admin\/clients\/(\d+)\/trial$/);
  if (mm && method === "PATCH") {
    const client = adminClients.find((c) => c.id === Number(mm![1]));
    if (!client) return notFound(path);
    if (body?.days_left !== undefined) {
      const d = Math.max(0, Number(body.days_left));
      client.trial_days_left = d;
      client.trial_active = true;
      client.trial_end = new Date(Date.now() + d * 86400000).toISOString();
    }
    if (body?.trial_active !== undefined) client.trial_active = !!body.trial_active;
    return client;
  }
  mm = m(/^\/api\/admin\/clients\/(\d+)\/contacts$/);
  if (mm && method === "POST") {
    const client = adminClients.find((c) => c.id === Number(mm![1]));
    if (!client) return notFound(path);
    client.contacts.push({
      id: ++contactSeq,
      name: body?.name ?? null,
      phone: body?.phone ?? null,
      email: body?.email ?? null,
    });
    return client;
  }
  mm = m(/^\/api\/admin\/clients\/(\d+)\/contacts\/(\d+)$/);
  if (mm && method === "DELETE") {
    const client = adminClients.find((c) => c.id === Number(mm![1]));
    if (!client) return notFound(path);
    client.contacts = client.contacts.filter((ct) => ct.id !== Number(mm![2]));
    return client;
  }

  // --- admin (other endpoints are stubbed in the demo) --------------------
  if (path.startsWith("/api/admin/")) {
    if (path.includes("stats")) return {};
    return [];
  }

  return notFound(path);
}

export async function demoRequest<T>(
  path: string,
  options: RequestInit,
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const body = options.body ? JSON.parse(options.body as string) : undefined;
  await delay(160);
  const cleanPath = path.split("?")[0];
  return route(method, cleanPath, body) as T;
}
