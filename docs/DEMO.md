# Live demo (GitHub Pages)

A clickable, shareable version of the whole product is published automatically
to **GitHub Pages** — no server, no sign-up, no credentials required.

## The URL

```
https://christianhillman15-afk.github.io/<repo>/
```

GitHub fills in the exact URL after the first deploy. You can always find it at:
**Repo → Settings → Pages**, or at the top of the latest
**Deploy demo to GitHub Pages** run under the **Actions** tab.

## How it works

- The frontend is built as a fully static site with
  `NEXT_PUBLIC_DEMO_MODE=true`. In that mode every API call is answered by an
  in-browser demo store (`frontend/lib/demo.ts`) instead of the real backend.
- Sample data is seeded for "Rivertown Plumbing Co." so you can click through
  everything: scan for leads, approve/decline replies, draft Business Posts,
  change plans, chat with support, edit settings, etc.
- It is **100% simulated** — nothing posts to Nextdoor or Facebook, no real
  emails or texts are sent, and no real customer data is involved. A page
  refresh resets the demo to its starting state.

## Deploying / updating it

The workflow `.github/workflows/deploy-demo.yml` runs on every push to the
working branch that touches `frontend/`. The first run also enables Pages
automatically.

If the first **deploy** step is blocked by an environment rule, allow the
branch once: **Settings → Environments → `github-pages` → Deployment branches**
→ add the working branch (or "All branches"). Re-run the job and the URL goes
live.

## This is the demo, not production

The demo exists so the product is instantly viewable. The real, full-stack app
(FastAPI backend + database + connectors + Stripe + SMS/email) deploys
separately — see `docs/GO-LIVE.md` and `render.yaml`.
