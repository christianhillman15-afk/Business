# Live demo — a clickable, shareable URL

A fully clickable version of the whole product runs as a **static site** with
**no backend, no sign-up, and no credentials**. Every API call is answered by an
in-browser demo store (`frontend/lib/demo.ts`) seeded with sample data for
"Rivertown Plumbing Co." so you can click through everything: scan for leads,
approve/decline replies, draft Business Posts, change plans, chat with support,
edit settings. It is **100% simulated** — nothing posts to Nextdoor/Facebook and
no real emails or texts are sent. A page refresh resets the demo.

The repo can stay **private** — the hosts below all support private repos.

## Option A — Netlify (recommended, keeps the repo private)

**Fastest, no build setup:** drag-and-drop the prebuilt site.
1. Build it (or use the zip already provided):
   `cd frontend && NEXT_PUBLIC_DEMO_MODE=true npx next build` → produces `frontend/out/`.
2. Go to <https://app.netlify.com/drop> and drag the `out` folder onto the page.
3. You get an instant `https://<random-name>.netlify.app` URL. Share it.

**Auto-updating (connect the repo):** this repo includes `netlify.toml`, so:
1. Netlify → **Add new site → Import an existing project** → pick this repo.
2. Netlify reads `netlify.toml` (base `frontend`, build `npm run build`,
   publish `out`, `NEXT_PUBLIC_DEMO_MODE=true`) — just click **Deploy**.
3. Every push to the connected branch rebuilds and redeploys automatically.

## Option B — Vercel (also private-friendly)

1. Vercel → **Add New → Project** → import this repo.
2. Set **Root Directory** = `frontend`.
3. Add an Environment Variable: `NEXT_PUBLIC_DEMO_MODE` = `true`.
4. Deploy → you get a `https://<name>.vercel.app` URL.

## Option C — GitHub Pages (only if the repo is public, or you have GitHub Pro)

The workflow `.github/workflows/deploy-demo.yml` is wired and ready, but GitHub
**cannot serve a private repo's Pages on the free plan**. If you make the repo
public (or upgrade to GitHub Pro), run that workflow from the **Actions** tab and
it publishes to `https://christianhillman15-afk.github.io/<repo>/`.

## This is the demo, not production

The demo exists so the product is instantly viewable. The real, full-stack app
(FastAPI backend + database + connectors + Stripe + SMS/email) deploys
separately — see `docs/GO-LIVE.md` and `render.yaml`.
