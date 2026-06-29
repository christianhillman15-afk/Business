"""A lightweight web dashboard for the whale bot.

Serves a single auto-refreshing web page (plus a small JSON API) so you can see
your paper account, open positions, settled results, and recent whale alerts in
a browser instead of the terminal. Uses only the Python standard library — no
extra installs.

Run with:  python -m whalebot dashboard
Then open: http://YOUR_SERVER_IP:8080
"""

from __future__ import annotations

import hmac
import json
import logging
import math
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .client import PolymarketClient
from .config import Config
from .paper import PaperPortfolio
from .state import State

log = logging.getLogger("whalebot.dashboard")

# Small in-process cache of {token_id: (price, fetched_at)} so refreshing the
# dashboard doesn't hammer the price API for the same open positions.
_price_cache: dict[str, tuple[float | None, float]] = {}
_PRICE_TTL = 30.0


def _cached_midpoint(client: PolymarketClient, token_id: str) -> float | None:
    now = time.time()
    hit = _price_cache.get(token_id)
    if hit and (now - hit[1]) < _PRICE_TTL:
        return hit[0]
    price = client.fetch_midpoint(token_id)
    _price_cache[token_id] = (price, now)
    return price


def _history_stats(settled, starting: float, now: float) -> dict:
    """Compute account-history metrics from the list of settled positions.

    Everything here is derived from each settled bet's ``pnl`` and ``settled_ts``
    (both already stored), so no extra files or daemon changes are needed.
    'Balance' is the realized/locked-in balance: starting + cumulative settled
    PnL (it ignores open-position price swings, which live on the Overview tab).
    """
    from collections import defaultdict

    s = sorted([p for p in settled if p.settled_ts], key=lambda p: p.settled_ts)

    def window_pnl(secs: float) -> float:
        return round(sum(p.pnl for p in s if now - p.settled_ts <= secs), 2)

    running = 0.0
    peak = starting
    for p in s:
        running += p.pnl
        peak = max(peak, starting + running)

    # Resolved bets (won/lost) drive the win/loss-flavored metrics; manual
    # sells still count toward money-over-time (windows/peak) but not these.
    resolved = [p for p in s if p.status in ("won", "lost")]
    res_pnls = [p.pnl for p in resolved]
    wins = [p.pnl for p in resolved if p.status == "won"]
    losses = [p.pnl for p in resolved if p.status == "lost"]

    days: dict[str, float] = defaultdict(float)
    for p in s:
        day = time.strftime("%Y-%m-%d", time.gmtime(p.settled_ts))
        days[day] += p.pnl

    streak = 0
    streak_type = ""
    for p in reversed(s):
        if p.status not in ("won", "lost"):
            continue  # manual sells aren't wins or losses
        t = "W" if p.status == "won" else "L"
        if not streak_type:
            streak_type, streak = t, 1
        elif t == streak_type:
            streak += 1
        else:
            break

    return {
        "starting_balance": round(starting, 2),
        "current_balance": round(starting + running, 2),
        "peak_balance": round(peak, 2),
        "all_time_pnl": round(running, 2),
        "drawdown_from_peak": round((starting + running) - peak, 2),
        "today": window_pnl(86_400),
        "week": window_pnl(7 * 86_400),
        "month": window_pnl(30 * 86_400),
        "year": window_pnl(365 * 86_400),
        "biggest_win": round(max(res_pnls), 2) if res_pnls else 0.0,
        "biggest_loss": round(min(res_pnls), 2) if res_pnls else 0.0,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "best_day": round(max(days.values()), 2) if days else 0.0,
        "worst_day": round(min(days.values()), 2) if days else 0.0,
        "total_settled": len(resolved),
        "total_wagered": round(sum(p.cost_usd for p in resolved), 2),
        "streak": streak,
        "streak_type": streak_type,
    }


_ADJ = [
    "Sneaky", "Reckless", "Greedy", "Lucky", "Degenerate", "Mysterious", "Caffeinated",
    "Feral", "Smug", "Paranoid", "Diamond-Handed", "Galaxy-Brain", "Sweaty", "Unhinged",
    "Mild-Mannered", "Suspicious", "Chonky", "Nocturnal", "Turbo", "Anonymous", "Brave",
    "Cold-Blooded", "Jittery", "Shadowy", "Fearless", "Reckless", "Hyperactive", "Zen",
]
_NOUN = [
    "Otter", "Walrus", "Goblin", "Whale", "Raccoon", "Llama", "Pigeon", "Badger",
    "Hamster", "Narwhal", "Possum", "Ferret", "Gecko", "Mongoose", "Capybara",
    "Platypus", "Squid", "Yak", "Moose", "Newt", "Penguin", "Wombat", "Lemur", "Sloth",
]
_TITLES = [
    "the Bold", "the Unlucky", "the Wise", "Jr.", "Sr.", "III", "the Great",
    "the Mysterious", "the Degenerate", "Esq.", "the Lucky", "the Menace",
]


def _funny_name(wallet: str) -> str:
    """Deterministic, stable funny nickname derived from a wallet address."""
    try:
        h = int(wallet, 16)
    except (TypeError, ValueError):
        h = sum(ord(c) for c in (wallet or "x"))
    adj = _ADJ[h % len(_ADJ)]
    noun = _NOUN[(h // 7) % len(_NOUN)]
    title = _TITLES[(h // 53) % len(_TITLES)]
    return f"{adj} {noun} {title}"


import re as _re

# Per-wallet enrichment cache: addr -> (data, fetched_at)
_suspect_cache: dict[str, tuple[dict, float]] = {}
_SUSPECT_TTL = 1800.0
# Per-wallet profile-URL cache: addr -> (url, fetched_at)
_url_cache: dict[str, tuple[str, float]] = {}
_URL_TTL = 3600.0
_HANDLE_RE = _re.compile(r"^[A-Za-z0-9_]{2,30}$")


def wallet_profile_url(client: PolymarketClient, wallet: str) -> str:
    """Canonical Polymarket profile URL for a wallet.

    Polymarket profiles live at /@<handle>; we resolve the handle from the
    wallet's trades. Wallets with no handle (auto '0x..-<ms>' pseudonyms) fall
    back to /profile/<address>, which Polymarket still resolves.
    """
    if not wallet:
        return ""
    now = time.time()
    hit = _url_cache.get(wallet)
    if hit and (now - hit[1]) < _URL_TTL:
        return hit[0]
    name = client.fetch_user_name(wallet)
    # A real handle is alphanumeric/underscore and not the '0x..-<digits>' form.
    if name and _HANDLE_RE.match(name) and not name.lower().startswith("0x"):
        url = f"https://polymarket.com/@{name}"
    else:
        url = f"https://polymarket.com/profile/{wallet}"
    _url_cache[wallet] = (url, now)
    return url


def enrich_suspect(client: PolymarketClient, wallet: str) -> dict:
    """Pull live Polymarket stats for a wallet (cached). Best-effort; any field
    may be None if Polymarket doesn't return it."""
    now = time.time()
    hit = _suspect_cache.get(wallet)
    if hit and (now - hit[1]) < _SUSPECT_TTL:
        return hit[0]

    value = client.fetch_user_value(wallet)
    pnl_all, pseudonym = client.fetch_user_profit(wallet, "all")
    pnl_1d, _ = client.fetch_user_profit(wallet, "1d")
    pnl_7d, _ = client.fetch_user_profit(wallet, "7d")
    pnl_30d, _ = client.fetch_user_profit(wallet, "30d")
    positions = client.fetch_user_positions(wallet, limit=500)

    # win rate from resolved positions (curPrice at 0/1, or redeemable)
    wins = losses = 0
    volume = 0.0
    for p in positions:
        try:
            volume += float(p.get("initialValue", 0) or 0)
            cur = float(p.get("curPrice", -1))
            resolved = p.get("redeemable") or cur in (0.0, 1.0)
            if resolved:
                rp = float(p.get("realizedPnl", 0) or 0)
                if rp > 0:
                    wins += 1
                elif rp < 0:
                    losses += 1
        except (TypeError, ValueError):
            continue
    settled = wins + losses
    win_rate = (wins / settled) if settled else None

    # account age from pseudonym '-<ms>' suffix
    age_days = None
    first_seen = ""
    if pseudonym and "-" in pseudonym:
        tail = pseudonym.rsplit("-", 1)[-1]
        if tail.isdigit():
            try:
                first_ms = int(tail)
                age_days = max(0.0, (now - first_ms / 1000.0) / 86400.0)
                first_seen = time.strftime("%Y-%m-%d", time.gmtime(first_ms / 1000.0))
            except (ValueError, OverflowError):
                pass

    data = {
        "wallet": wallet,
        "profile_url": wallet_profile_url(client, wallet),
        "value": round(value, 2) if value is not None else None,
        "pnl_all": round(pnl_all, 2) if pnl_all is not None else None,
        "pnl_1d": round(pnl_1d, 2) if pnl_1d is not None else None,
        "pnl_7d": round(pnl_7d, 2) if pnl_7d is not None else None,
        "pnl_30d": round(pnl_30d, 2) if pnl_30d is not None else None,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "wins": wins,
        "losses": losses,
        "volume": round(volume, 2),
        "markets_traded": len(positions),
        "age_days": round(age_days, 1) if age_days is not None else None,
        "first_seen": first_seen,
    }
    _suspect_cache[wallet] = (data, now)
    return data


def _suspicion(flags: int, usd: float, markets: int, span_s: float) -> list[str]:
    """Return human-readable red flags for a wallet. A wallet is considered
    'very obviously suspicious' only when it trips 2+ of these."""
    reasons = []
    if flags >= 3:
        reasons.append(f"flagged {flags}× (repeat offender)")
    if usd >= 25_000:
        reasons.append(f"${usd:,.0f} in flagged buys")
    if markets >= 5:
        reasons.append(f"hit {markets} different markets")
    if flags >= 4 and 0 < span_s < 3600:
        reasons.append("burst of buys within an hour")
    if usd >= 100_000:
        reasons.append("six-figure flagged volume")
    return reasons


def build_suspects(state) -> list[dict]:
    """The tracked suspect list from our own observations (no external calls)."""
    out = []
    for wallet, rec in state.suspects.items():
        flags = rec.get("flags", 0)
        usd = round(rec.get("usd", 0.0), 2)
        markets = len(rec.get("markets", []))
        span = rec.get("last_ts", 0) - rec.get("first_ts", 0)
        reasons = _suspicion(flags, usd, markets, span)
        out.append(
            {
                "wallet": wallet,
                "name": _funny_name(wallet),
                "flags": flags,
                "flagged_usd": usd,
                "markets": markets,
                "first_ts": rec.get("first_ts", 0),
                "first_iso": time.strftime(
                    "%Y-%m-%d", time.gmtime(rec.get("first_ts", 0))
                )
                if rec.get("first_ts")
                else "",
                "suspicion": len(reasons),
                "reasons": reasons,
            }
        )
    out.sort(key=lambda s: s["flagged_usd"], reverse=True)
    return out


def _category(title: str, slug: str) -> str:
    """Best-effort market category from the title/slug (heuristic)."""
    t = f"{title} {slug}".lower()
    if any(k in t for k in ("updown", "bitcoin", "ethereum", " btc", " eth", "solana", "dogecoin", " up or down")):
        return "Crypto"
    if any(k in t for k in (" vs.", " vs ", "fifwc", "nba", "mlb", "nfl", "nhl", "ucl",
                            "match", "o/u", "spread", "win on", "world cup", "super bowl",
                            "premier league", "champions", "playoff", "f1", "grand prix")):
        return "Sports"
    if any(k in t for k in ("president", "election", "senate", "congress", "governor",
                            "primary", "nominee", "nomination", "prime minister", "parliament",
                            "referendum", "impeach")):
        return "Politics"
    return "Other"


def _breakdown(closed) -> dict:
    """Group settled positions by signal type and by category for win rates."""
    from collections import defaultdict

    def group(keyfn):
        buckets: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
        for p in closed:
            b = buckets[keyfn(p)]
            b["pnl"] += p.pnl
            if p.status == "won":
                b["wins"] += 1
            elif p.status == "lost":
                b["losses"] += 1
        rows = []
        for name, b in buckets.items():
            resolved = b["wins"] + b["losses"]
            rows.append({
                "name": name,
                "resolved": resolved,
                "wins": b["wins"],
                "losses": b["losses"],
                "win_rate": round(b["wins"] / resolved, 4) if resolved else None,
                "pnl": round(b["pnl"], 2),
            })
        rows.sort(key=lambda r: r["pnl"], reverse=True)
        return rows

    return {
        "by_signal": group(lambda p: p.signal_kind or "unknown"),
        "by_category": group(lambda p: _category(p.title, p.event_slug or p.slug)),
    }


def _market_url(event_slug: str, slug: str) -> str:
    """Build a polymarket.com link from a market's slug (best-effort)."""
    s = (event_slug or slug or "").strip()
    return f"https://polymarket.com/event/{s}" if s else ""


def _tail_jsonl(path: str, limit: int) -> list[dict]:
    """Read the last ``limit`` JSON objects from a .jsonl file (best-effort)."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception as exc:  # noqa: BLE001
        log.debug("could not read %s: %s", path, exc)
        return []
    out: list[dict] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    out.reverse()  # newest first
    return out


def build_snapshot(cfg: Config, client: PolymarketClient | None = None) -> dict:
    """Assemble the full dashboard payload from the bot's saved files.

    For open positions we also pull the live mid-market price so the dashboard
    can show current value and unrealized profit/loss (whether you're up or down
    right now), not just what you paid.
    """
    # Reload state fresh each call so the dashboard reflects the live daemon.
    state = State(cfg.state.path, cfg.state.dedup_ttl_minutes)
    portfolio = PaperPortfolio(cfg.paper, state.paper)
    client = client or PolymarketClient(
        cfg.polymarket.data_api, cfg.polymarket.gamma_api, cfg.polymarket.clob_api
    )

    positions = sorted(
        portfolio.positions.values(), key=lambda p: p.opened_ts, reverse=True
    )
    open_pos = [p for p in positions if p.status == "open"]
    closed_pos = [p for p in positions if p.status in ("won", "lost", "sold")]

    def _iso(ts):
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts)) if ts else ""

    def settled_dict(p):
        return {
            "id": p.id,
            "title": p.title,
            "url": _market_url(p.event_slug, p.slug),
            "outcome": p.outcome,
            "signal": p.signal_kind,
            "entry_price": round(p.entry_price, 3),
            "shares": round(p.shares, 1),
            "cost_usd": round(p.cost_usd, 2),
            "status": p.status,
            "pnl": round(p.pnl, 2),
            "asset": p.asset,
            "opened_ts": p.opened_ts,
            "opened_iso": _iso(p.opened_ts),
            "settled_iso": _iso(p.settled_ts),
            "wallets": list(getattr(p, "wallets", []) or []),
        }

    open_rows = []
    unrealized_total = 0.0
    live_value_total = 0.0
    for p in open_pos:
        price = _cached_midpoint(client, p.asset)
        if price is not None:
            cur_value = p.shares * price
            unreal = cur_value - p.cost_usd
            unrealized_total += unreal
            live_value_total += cur_value
        else:
            cur_value = None
            unreal = None
            live_value_total += p.cost_usd  # fall back to cost when no price
        open_rows.append(
            {
                "id": p.id,
                "title": p.title,
                "url": _market_url(p.event_slug, p.slug),
                "outcome": p.outcome,
                "signal": p.signal_kind,
                "entry_price": round(p.entry_price, 3),
                "current_price": round(price, 3) if price is not None else None,
                "shares": round(p.shares, 1),
                "cost_usd": round(p.cost_usd, 2),
                "current_value": round(cur_value, 2) if cur_value is not None else None,
                "unrealized_pnl": round(unreal, 2) if unreal is not None else None,
                "asset": p.asset,
                "opened_ts": p.opened_ts,
                "opened_iso": _iso(p.opened_ts),
                "wallets": list(getattr(p, "wallets", []) or []),
            }
        )

    stats = portfolio.stats()
    # Live equity = cash + current market value of open positions.
    stats["live_equity"] = round(stats["cash"] + live_value_total, 2)
    stats["unrealized_pnl"] = round(unrealized_total, 2)

    return {
        "stats": stats,
        "history": _history_stats(closed_pos, cfg.paper.starting_balance, time.time()),
        "breakdown": _breakdown(closed_pos),
        "open_positions": open_rows,
        "settled_positions": [settled_dict(p) for p in closed_pos][:50],
        "alerts": _tail_jsonl(cfg.notifications.file.path, cfg.dashboard.recent_alerts),
        "refresh_seconds": cfg.dashboard.refresh_seconds,
    }


def _make_handler(cfg: Config):
    token = cfg.dashboard.token
    client = PolymarketClient(
        cfg.polymarket.data_api, cfg.polymarket.gamma_api, cfg.polymarket.clob_api
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default noisy logging
            pass

        def _authorized(self, query: dict) -> bool:
            if not token:
                return True
            return hmac.compare_digest(query.get("token", [""])[0], token)

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if not self._authorized(query):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden: missing or wrong ?token=")
                return

            if parsed.path == "/api/data":
                self._send_json(build_snapshot(cfg, client))
            elif parsed.path == "/api/history":
                tok = query.get("m", [""])[0]
                iv = query.get("iv", ["1d"])[0]
                if iv not in ("1h", "6h", "1d", "1w", "max"):
                    iv = "1d"
                self._send_json({"history": client.fetch_price_history(tok, interval=iv)})
            elif parsed.path == "/api/suspects":
                state = State(cfg.state.path, cfg.state.dedup_ttl_minutes)
                self._send_json({"suspects": build_suspects(state)})
            elif parsed.path == "/api/suspect":
                w = query.get("w", [""])[0].lower()
                self._send_json(enrich_suspect(client, w) if w else {})
            elif parsed.path == "/api/walleturl":
                w = query.get("w", [""])[0].lower()
                self._send_json({"url": wallet_profile_url(client, w) if w else ""})
            elif parsed.path in ("/", "/index.html"):
                self._send_html(PAGE)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if not self._authorized(query):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden")
                return
            if parsed.path != "/api/order":
                self.send_response(404)
                self.end_headers()
                return
            # State-mutating endpoint: require a configured token so a default
            # (token-less) deployment can't be traded by anyone who finds it.
            if not token:
                self._send_json({"ok": False, "error": "set a dashboard token to enable trading"})
                return
            # Cap the request body so a huge Content-Length can't exhaust memory.
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except (TypeError, ValueError):
                length = 0
            if length < 0 or length > 8192:
                self._send_json({"ok": False, "error": "body too large"})
                return
            # Bound the number of pending command files (disk / per-tick DoS).
            cdir = cfg.paper.commands_dir
            try:
                pending = len([f for f in os.listdir(cdir) if f.endswith(".json")]) if os.path.isdir(cdir) else 0
            except OSError:
                pending = 0
            if pending >= 200:
                self._send_json({"ok": False, "error": "too many pending orders; try again shortly"})
                return
            try:
                body = self.rfile.read(length) if length else b"{}"
                cmd = json.loads(body or b"{}")
            except Exception:  # noqa: BLE001
                self._send_json({"ok": False, "error": "bad json"})
                return

            action = str(cmd.get("action", "")).lower()
            pid = str(cmd.get("position_id", ""))
            if action not in ("buy", "sell") or not pid:
                self._send_json({"ok": False, "error": "need action buy|sell and position_id"})
                return
            out = {"action": action, "position_id": pid, "ts": time.time()}
            if action == "buy":
                try:
                    usd = float(cmd.get("usd", 0))
                except (TypeError, ValueError):
                    usd = 0.0
                if not math.isfinite(usd) or usd <= 0:
                    self._send_json({"ok": False, "error": "usd must be a positive number"})
                    return
                out["usd"] = round(usd, 2)
            else:
                try:
                    frac = float(cmd.get("fraction", 1.0))
                except (TypeError, ValueError):
                    frac = 1.0
                if not math.isfinite(frac):
                    frac = 1.0
                out["fraction"] = max(0.0, min(1.0, frac))

            try:
                os.makedirs(cdir, exist_ok=True)
                fn = os.path.join(cdir, f"cmd_{uuid.uuid4().hex}.json")
                tmp = fn + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(out, fh)
                os.replace(tmp, fn)  # atomic; bot won't read a half-written file
            except Exception as exc:  # noqa: BLE001
                self._send_json({"ok": False, "error": str(exc)})
                return
            self._send_json({"ok": True, "queued": out})

        def _send_json(self, payload: dict):
            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str):
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def run_dashboard(cfg: Config) -> None:
    handler = _make_handler(cfg)
    server = ThreadingHTTPServer((cfg.dashboard.host, cfg.dashboard.port), handler)
    where = f"http://{cfg.dashboard.host}:{cfg.dashboard.port}"
    log.info("dashboard running at %s (Ctrl+C to stop)", where)
    if cfg.dashboard.token:
        log.info("access requires ?token=%s", cfg.dashboard.token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("dashboard stopping…")
    finally:
        server.server_close()


# The page is a single self-contained HTML/JS file. It calls /api/data on a
# timer and re-renders. The token (if any) is read from the page's own URL so
# the API calls stay authorized.
PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Whale Bot · Polymarket Signal Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{
    color-scheme: dark;
    --bg:#070b16; --bg2:#0c1322; --panel:#0f1729; --panel2:#131d33;
    --line:#1e2a44; --line2:#26324f;
    --txt:#eaf0fb; --muted:#8b9bbd; --dim:#5d6e92;
    --green:#34d399; --green-bg:#0e2e22; --red:#f87171; --red-bg:#2e1620;
    --amber:#fbbf24; --blue:#60a5fa; --accent:#5eead4;
    --shadow:0 8px 30px rgba(0,0,0,.35);
  }
  *{ box-sizing:border-box; }
  html,body{ margin:0; }
  body{
    font-family:'Inter',-apple-system,system-ui,Segoe UI,Roboto,sans-serif;
    color:var(--txt); -webkit-font-smoothing:antialiased;
    background:
      radial-gradient(1200px 600px at 80% -10%, rgba(94,234,212,.07), transparent 60%),
      radial-gradient(1000px 500px at 0% 0%, rgba(96,165,250,.06), transparent 55%),
      var(--bg);
    min-height:100vh;
  }
  .topbar{
    position:sticky; top:0; z-index:10; backdrop-filter:blur(10px);
    background:rgba(8,12,22,.72); border-bottom:1px solid var(--line);
    padding:14px 22px; display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;
  }
  .brand{ display:flex; align-items:center; gap:12px; }
  .logo{
    width:38px; height:38px; border-radius:11px; display:grid; place-items:center; font-size:20px;
    background:linear-gradient(135deg,#0ea5a0,#2563eb); box-shadow:0 4px 14px rgba(37,99,235,.4);
  }
  .brand h1{ font-size:16px; font-weight:700; margin:0; letter-spacing:.2px; }
  .brand .sub{ font-size:12px; color:var(--muted); margin-top:1px; }
  .status{ display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); }
  .dot{ width:8px; height:8px; border-radius:50%; background:var(--green);
        box-shadow:0 0 0 0 rgba(52,211,153,.6); animation:pulse 2s infinite; }
  .dot.off{ background:var(--red); animation:none; }
  @keyframes pulse{ 0%{box-shadow:0 0 0 0 rgba(52,211,153,.5);} 70%{box-shadow:0 0 0 7px rgba(52,211,153,0);} 100%{box-shadow:0 0 0 0 rgba(52,211,153,0);} }

  .wrap{ padding:24px 22px 60px; max-width:1140px; margin:0 auto; }

  /* hero */
  .hero{
    display:flex; align-items:flex-end; justify-content:space-between; gap:18px; flex-wrap:wrap;
    background:linear-gradient(135deg,var(--panel),var(--bg2)); border:1px solid var(--line);
    border-radius:18px; padding:22px 24px; box-shadow:var(--shadow); margin-bottom:18px;
  }
  .hero .label{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }
  .hero .big{ font-size:40px; font-weight:800; margin-top:6px; letter-spacing:-.5px; }
  .hero .meta{ display:flex; gap:18px; flex-wrap:wrap; margin-top:6px; font-size:13px; color:var(--muted); }
  .badge{ display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:999px;
          font-weight:700; font-size:13px; }
  .badge.pos{ background:var(--green-bg); color:var(--green); }
  .badge.neg{ background:var(--red-bg); color:var(--red); }

  /* tabs */
  .tabs{ display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 18px; }
  .tab{ padding:9px 16px; cursor:pointer; color:var(--muted); font-size:13.5px; font-weight:600;
        border:1px solid var(--line); background:var(--panel); border-radius:999px; transition:.15s; }
  .tab:hover{ color:var(--txt); border-color:var(--line2); }
  .tab.active{ color:#04110d; background:linear-gradient(135deg,#5eead4,#34d399); border-color:transparent; }
  .tab .count{ font-size:11px; opacity:.7; margin-left:5px; }
  .panel{ display:none; animation:fade .25s ease; }
  .panel.active{ display:block; }
  @keyframes fade{ from{opacity:0; transform:translateY(4px);} to{opacity:1; transform:none;} }

  .section-title{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em;
                  font-weight:700; margin:22px 2px 12px; }
  .section-title:first-child{ margin-top:4px; }
  /* stat cards */
  .cards{ display:grid; grid-template-columns:repeat(auto-fit,minmax(168px,1fr)); gap:14px; }
  .card{ position:relative; overflow:hidden; background:var(--panel); border:1px solid var(--line);
         border-radius:14px; padding:16px 16px 15px; transition:.18s; }
  .card:hover{ transform:translateY(-2px); border-color:var(--line2); box-shadow:var(--shadow); }
  .card::before{ content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--blue); opacity:.8; }
  .card.green::before{ background:var(--green); } .card.red::before{ background:var(--red); }
  .card.amber::before{ background:var(--amber); } .card.teal::before{ background:var(--accent); }
  .card .label{ font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }
  .card .value{ font-size:25px; font-weight:700; margin-top:7px; letter-spacing:-.3px; }
  .card .hint{ font-size:11px; color:var(--dim); margin-top:3px; }
  .pos{ color:var(--green); } .neg{ color:var(--red); }

  /* tables */
  .tablecard{ background:var(--panel); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
  table{ width:100%; border-collapse:collapse; font-size:13px; }
  thead th{ position:sticky; top:0; background:var(--panel2); color:var(--muted); font-weight:600;
            text-align:left; padding:11px 14px; border-bottom:1px solid var(--line); font-size:11.5px;
            text-transform:uppercase; letter-spacing:.04em; }
  td{ padding:12px 14px; border-bottom:1px solid var(--line); }
  tbody tr:last-child td{ border-bottom:none; }
  tbody tr:hover td{ background:rgba(255,255,255,.02); }
  td.num, th.num{ text-align:right; font-variant-numeric:tabular-nums; }
  .mkt{ max-width:360px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .mktlink{ color:var(--txt); text-decoration:underline; text-decoration-color:var(--line2);
            text-underline-offset:3px; transition:.15s; }
  .mktlink:hover{ color:var(--accent); text-decoration-color:var(--accent); }
  .pill{ padding:3px 9px; border-radius:999px; font-size:11px; font-weight:700; white-space:nowrap; }
  .pill.high{ background:var(--red-bg); color:var(--red); }
  .pill.medium{ background:#352a10; color:var(--amber); }
  .pill.low,.pill.watchlist{ background:#10233b; color:var(--blue); }
  .pill.won,.pill.up{ background:var(--green-bg); color:var(--green); }
  .pill.lost,.pill.down{ background:var(--red-bg); color:var(--red); }
  .pill.sold{ background:#2a2f10; color:#ffd27a; }
  .empty{ color:var(--dim); padding:34px 16px; text-align:center; font-style:italic; }
  footer{ text-align:center; color:var(--dim); font-size:12px; padding:28px 16px 8px; }
  tr.clickrow{ cursor:pointer; }
  tr.clickrow:hover td{ background:rgba(94,234,212,.06); }

  /* modal */
  .overlay{ position:fixed; inset:0; background:rgba(3,6,12,.7); backdrop-filter:blur(3px);
            display:none; align-items:flex-start; justify-content:center; z-index:50; padding:28px 14px; overflow:auto; }
  .overlay.show{ display:flex; }
  .modal{ width:100%; max-width:720px; background:var(--panel); border:1px solid var(--line2);
          border-radius:18px; box-shadow:var(--shadow); overflow:hidden; animation:fade .2s ease; }
  .modal .mhead{ display:flex; align-items:flex-start; justify-content:space-between; gap:12px;
                 padding:18px 20px; border-bottom:1px solid var(--line); }
  .modal .mhead h3{ margin:0; font-size:17px; }
  .modal .mhead .msub{ font-size:12.5px; color:var(--muted); margin-top:4px; }
  .xbtn{ background:var(--panel2); border:1px solid var(--line2); color:var(--muted); border-radius:9px;
         width:32px; height:32px; font-size:16px; cursor:pointer; flex:none; }
  .xbtn:hover{ color:var(--txt); }
  .mbody{ padding:18px 20px 22px; }
  .mgrid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:10px; margin-bottom:8px; }
  .mstat{ background:var(--bg2); border:1px solid var(--line); border-radius:11px; padding:11px 12px; }
  .mstat .l{ font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
  .mstat .v{ font-size:18px; font-weight:700; margin-top:3px; }
  .ivbar{ display:flex; gap:6px; margin:18px 0 8px; }
  .ivbtn{ font-size:12px; font-weight:600; color:var(--muted); background:var(--panel2);
          border:1px solid var(--line); border-radius:8px; padding:5px 11px; cursor:pointer; }
  .ivbtn.active{ color:#04110d; background:var(--accent); border-color:transparent; }
  .chartwrap{ position:relative; }
  .chartwrap svg{ width:100%; height:auto; display:block; }
  .ctip{ position:absolute; pointer-events:none; background:#0a1424; border:1px solid var(--line2);
         border-radius:8px; padding:6px 9px; font-size:12px; color:var(--txt); white-space:nowrap;
         transform:translate(-50%,-130%); display:none; z-index:2; }
  .msec{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em;
         font-weight:700; margin:20px 0 10px; }
  .wallets{ display:flex; flex-direction:column; gap:8px; }
  .wallet{ display:flex; align-items:center; justify-content:space-between; gap:10px;
           background:var(--bg2); border:1px solid var(--line); border-radius:10px; padding:9px 12px; }
  .wallet code{ font-size:12.5px; color:var(--blue); }
  .wallet a{ font-size:12px; color:var(--accent); text-decoration:none; font-weight:600; white-space:nowrap; }
  .wallet a:hover{ text-decoration:underline; }
  .wrapbar{ flex-wrap:wrap; }
  /* suspect cards */
  .suspects-grid{ display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:14px; }
  .suspect{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:15px 16px;
            cursor:pointer; transition:.16s; position:relative; overflow:hidden; }
  .suspect:hover{ transform:translateY(-2px); border-color:var(--accent); box-shadow:var(--shadow); }
  .suspect .av{ width:36px; height:36px; border-radius:50%; display:grid; place-items:center; font-size:18px;
                background:linear-gradient(135deg,#1f3a5f,#0e2e22); margin-bottom:10px; }
  .suspect .nm{ font-weight:700; font-size:15px; }
  .suspect .ad{ font-size:11px; color:var(--dim); margin-top:2px; font-family:ui-monospace,monospace; }
  .suspect .row{ display:flex; justify-content:space-between; font-size:12.5px; margin-top:9px; color:var(--muted); }
  .suspect .row b{ color:var(--txt); font-weight:600; }
  .suspect .hl{ position:absolute; top:12px; right:14px; font-size:13px; font-weight:800; }
  .ivbtn.sus{ border-color:#5a2330; color:#ff8ba0; }
  .ivbtn.sus.active{ background:linear-gradient(135deg,#f87171,#ef4444); color:#1a0608; border-color:transparent; }
  .suspect.flagged{ border-color:#5a2330; }
  .suspect.flagged::after{ content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--red); }
  .reasons{ margin-top:10px; display:flex; flex-direction:column; gap:5px; }
  .reason{ font-size:11.5px; color:#ff8ba0; background:var(--red-bg); border-radius:7px; padding:4px 8px; }
  .sdesc{ background:var(--bg2); border:1px solid var(--line); border-radius:11px; padding:13px 15px;
          font-size:13.5px; line-height:1.5; color:var(--txt); margin-bottom:14px; }
  .bigbtn{ display:block; text-align:center; margin-top:18px; padding:11px; border-radius:11px;
           background:linear-gradient(135deg,#5eead4,#34d399); color:#04110d; font-weight:700;
           text-decoration:none; }
  .bigbtn:hover{ filter:brightness(1.05); }
  /* buy/sell controls */
  .actions{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .actions input, .actions select{ background:var(--bg2); border:1px solid var(--line2); color:var(--txt);
    border-radius:9px; padding:9px 11px; font-size:13px; min-width:96px; }
  .actbtn{ border:none; border-radius:9px; padding:9px 16px; font-weight:700; font-size:13px; cursor:pointer; }
  .actbtn.buy{ background:linear-gradient(135deg,#34d399,#10b981); color:#04110d; }
  .actbtn.sell{ background:linear-gradient(135deg,#f87171,#ef4444); color:#1a0608; }
  .actbtn:hover{ filter:brightness(1.06); }
  .actbtn:disabled{ opacity:.5; cursor:default; }
  .actmsg{ font-size:12.5px; color:var(--muted); margin-top:9px; min-height:16px; }
  .actmsg.ok{ color:var(--green); } .actmsg.err{ color:var(--red); }
  .papertag{ font-size:10px; font-weight:700; color:var(--amber); background:#352a10;
    border-radius:6px; padding:2px 7px; margin-left:8px; vertical-align:middle; }
</style>
</head>
<body>
<div class="topbar">
  <div class="brand">
    <div class="logo">🐋</div>
    <div>
      <h1>Whale&nbsp;Bot</h1>
      <div class="sub">Polymarket signal tracker</div>
    </div>
  </div>
  <div class="status"><span class="dot" id="dot"></span><span id="updated">connecting…</span></div>
</div>

<div class="wrap">
  <div class="hero">
    <div>
      <div class="label">Live equity</div>
      <div class="big" id="heroEquity">—</div>
      <div class="meta">
        <span id="heroStart"></span><span id="heroCash"></span><span id="heroWin"></span>
      </div>
    </div>
    <div id="heroBadge"></div>
  </div>

  <div class="tabs" id="tabs">
    <button class="tab active" data-tab="overview">Overview</button>
    <button class="tab" data-tab="positions">Current Positions<span class="count" id="c-pos"></span></button>
    <button class="tab" data-tab="history">Account History</button>
    <button class="tab" data-tab="suspects">Suspects<span class="count" id="c-sus"></span></button>
    <button class="tab" data-tab="alerts">Alerts<span class="count" id="c-al"></span></button>
    <button class="tab" data-tab="settled">Settled<span class="count" id="c-st"></span></button>
  </div>

  <div class="panel active" id="overview"><div class="cards" id="cards"></div></div>
  <div class="panel" id="positions"><div class="tablecard" id="open"></div></div>
  <div class="panel" id="history">
    <div class="section-title">Balance</div>
    <div class="cards" id="histTop"></div>
    <div class="section-title">Performance over time</div>
    <div class="cards" id="histTime"></div>
    <div class="section-title">Trade stats</div>
    <div class="cards" id="histStats"></div>
    <div class="section-title">Win rate by signal type</div>
    <div class="tablecard" id="bdSignal"></div>
    <div class="section-title">Win rate by market category</div>
    <div class="tablecard" id="bdCategory"></div>
  </div>
  <div class="panel" id="suspects">
    <div class="ivbar wrapbar" id="suspectCats">
      <button class="ivbtn sus" data-cat="suspicious">🚩 Most Suspicious</button>
      <button class="ivbtn active" data-cat="biggest">💵 Biggest Buyer</button>
      <button class="ivbtn" data-cat="heavy">🔁 Heavy Buyer</button>
      <button class="ivbtn" data-cat="active">⚡ Most Active</button>
      <button class="ivbtn" data-cat="richest">💰 Richest</button>
      <button class="ivbtn" data-cat="profit">📈 Most Profitable</button>
      <button class="ivbtn" data-cat="winrate">🎯 Highest Win Rate</button>
    </div>
    <div id="suspectsList"><div class="empty">Open this tab to load suspects…</div></div>
  </div>
  <div class="panel" id="alerts"><div class="tablecard" id="alertsBody"></div></div>
  <div class="panel" id="settled"><div class="tablecard" id="settledBody"></div></div>
</div>
<div class="overlay" id="overlay">
  <div class="modal" id="modal">
    <div class="mhead">
      <div>
        <h3 id="dTitle">—</h3>
        <div class="msub" id="dSub"></div>
      </div>
      <button class="xbtn" id="dClose">✕</button>
    </div>
    <div class="mbody">
      <div class="mgrid" id="dStats"></div>
      <div id="dActions"></div>
      <div class="msec">Live price (Polymarket)</div>
      <div class="ivbar" id="dIv">
        <button class="ivbtn" data-iv="6h">6h</button>
        <button class="ivbtn active" data-iv="1d">1D</button>
        <button class="ivbtn" data-iv="1w">1W</button>
        <button class="ivbtn" data-iv="max">All</button>
      </div>
      <div class="chartwrap" id="dChart"><div class="empty">Loading chart…</div></div>
      <div class="msec">Whale wallet(s) that triggered this flag</div>
      <div class="wallets" id="dWallets"></div>
    </div>
  </div>
</div>

<div class="overlay" id="soverlay">
  <div class="modal" id="smodal">
    <div class="mhead">
      <div>
        <h3 id="sTitle">—</h3>
        <div class="msub" id="sSub"></div>
      </div>
      <button class="xbtn" id="sClose">✕</button>
    </div>
    <div class="mbody">
      <div id="sDesc" class="sdesc"></div>
      <div id="sReasons"></div>
      <div class="mgrid" id="sStats"></div>
      <div class="msec">PnL over time (Polymarket)</div>
      <div class="mgrid" id="sPnl"></div>
      <div class="msec">What we've seen them do</div>
      <div class="mgrid" id="sOurs"></div>
      <a id="sProfile" class="bigbtn" href="#" target="_blank" rel="noopener">Open trader on Polymarket ↗</a>
    </div>
  </div>
</div>

<footer>Auto-refreshing · paper trading (fake money) · powered by your Polymarket whale bot</footer>

<script>
const TOKEN = new URLSearchParams(location.search).get('token') || '';
const api = '/api/data' + (TOKEN ? ('?token=' + encodeURIComponent(TOKEN)) : '');

function money(n){ if(n==null) return '—';
  return (n<0?'-$':'$') + Math.abs(Number(n)).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
function pct(n){ return (n>=0?'+':'') + (n*100).toFixed(1) + '%'; }
function signClass(n){ return n > 0 ? 'pos' : (n < 0 ? 'neg' : ''); }
function esc(s){ return String(s==null?'':s).replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function pmUrl(o){ return o.url || ((o.event_slug||o.slug) ? ('https://polymarket.com/event/'+(o.event_slug||o.slug)) : ''); }
function mktCell(title, url){
  const t = esc(title);
  return url ? `<a class="mktlink" href="${esc(url)}" target="_blank" rel="noopener" title="${t} — open on Polymarket">${t} ↗</a>`
             : t;
}
function card(label, value, cls, accent, hint){
  return `<div class="card ${accent||''}"><div class="label">${label}</div>
    <div class="value ${cls||''}">${value}</div>${hint?`<div class="hint">${hint}</div>`:''}</div>`;
}
function wrapTable(head, rows, empty){
  return rows ? `<table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`
             : `<div class="empty">${empty}</div>`;
}

document.getElementById('tabs').addEventListener('click', e=>{
  const btn = e.target.closest('.tab'); if(!btn) return;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(btn.dataset.tab).classList.add('active');
  if(btn.dataset.tab==='suspects') loadSuspects();
});

function render(d){
  window.DATA = d;  // so the detail-modal click handler can look up positions
  const s = d.stats;
  const totalPnl = s.live_equity - s.starting_balance;

  // hero
  document.getElementById('heroEquity').textContent = money(s.live_equity);
  document.getElementById('heroStart').textContent = 'Started ' + money(s.starting_balance);
  document.getElementById('heroCash').textContent = 'Cash ' + money(s.cash);
  document.getElementById('heroWin').textContent = 'Win rate ' + (s.win_rate*100).toFixed(1) + '%';
  document.getElementById('heroBadge').innerHTML =
    `<span class="badge ${totalPnl>=0?'pos':'neg'}">${totalPnl>=0?'▲':'▼'} ${money(totalPnl)} · ${pct(s.roi)}</span>`;

  // overview cards
  document.getElementById('cards').innerHTML =
    card('Win rate', (s.win_rate*100).toFixed(1)+'%', '', 'teal', s.settled_trades+' settled') +
    card('Live equity', money(s.live_equity), signClass(totalPnl), 'green') +
    card('Open P&L (now)', money(s.unrealized_pnl), signClass(s.unrealized_pnl), s.unrealized_pnl>=0?'green':'red', 'unrealized') +
    card('Realized PnL', money(s.realized_pnl), signClass(s.realized_pnl), s.realized_pnl>=0?'green':'red', 'from settled') +
    card('Record', s.wins+'W / '+s.losses+'L', '', 'amber') +
    card('Open positions', s.open_positions, '', 'blue') +
    card('Cash', money(s.cash), '', 'blue') +
    card('ROI', pct(s.roi), signClass(s.roi), s.roi>=0?'green':'red');

  // ACCOUNT HISTORY
  const h = d.history;
  if (h){
    const ddCls = h.drawdown_from_peak < 0 ? 'red' : 'green';
    document.getElementById('histTop').innerHTML =
      card('Peak balance', money(h.peak_balance), '', 'teal', 'highest ever') +
      card('Current balance', money(h.current_balance), signClass(h.all_time_pnl), h.all_time_pnl>=0?'green':'red', 'realized') +
      card('All-time P&L', money(h.all_time_pnl), signClass(h.all_time_pnl), h.all_time_pnl>=0?'green':'red', h.total_settled+' settled') +
      card('Down from peak', money(h.drawdown_from_peak), signClass(h.drawdown_from_peak), ddCls);
    document.getElementById('histTime').innerHTML =
      card('Today', money(h.today), signClass(h.today), h.today>=0?'green':'red') +
      card('This week', money(h.week), signClass(h.week), h.week>=0?'green':'red') +
      card('This month', money(h.month), signClass(h.month), h.month>=0?'green':'red') +
      card('This year', money(h.year), signClass(h.year), h.year>=0?'green':'red');
    const streak = h.streak ? (h.streak + (h.streak_type==='W'?' wins':' losses')) : '—';
    document.getElementById('histStats').innerHTML =
      card('Biggest win', money(h.biggest_win), 'pos', 'green') +
      card('Biggest loss', money(h.biggest_loss), 'neg', 'red') +
      card('Avg win', money(h.avg_win), 'pos', 'green') +
      card('Avg loss', money(h.avg_loss), 'neg', 'red') +
      card('Best day', money(h.best_day), signClass(h.best_day), 'green') +
      card('Worst day', money(h.worst_day), signClass(h.worst_day), 'red') +
      card('Current streak', streak, h.streak_type==='W'?'pos':(h.streak_type==='L'?'neg':''), 'amber') +
      card('Total wagered', money(h.total_wagered), '', 'blue', h.total_settled+' bets');
  }
  // breakdown tables (win rate by signal / category)
  const bd = d.breakdown||{by_signal:[],by_category:[]};
  const bdRows = rows => rows.length ? wrapTable(
    `<th>Group</th><th class="num">Resolved</th><th class="num">W/L</th><th class="num">Win rate</th><th class="num">PnL</th>`,
    rows.map(r=>`<tr><td>${esc(r.name)}</td><td class="num">${r.resolved}</td>
      <td class="num">${r.wins}/${r.losses}</td>
      <td class="num">${r.win_rate==null?'—':(r.win_rate*100).toFixed(0)+'%'}</td>
      <td class="num ${signClass(r.pnl)}">${money(r.pnl)}</td></tr>`).join(''),
    'Nothing settled yet.') : '<div class="empty">Nothing settled yet.</div>';
  document.getElementById('bdSignal').innerHTML = bdRows(bd.by_signal||[]);
  document.getElementById('bdCategory').innerHTML = bdRows(bd.by_category||[]);

  // current positions
  const op = d.open_positions;
  document.getElementById('c-pos').textContent = op.length ? op.length : '';
  document.getElementById('open').innerHTML = wrapTable(
    `<th class="mkt">Market</th><th>Pick</th><th class="num">Entry</th><th class="num">Now</th>
     <th class="num">Cost</th><th class="num">Value</th><th class="num">P&L</th><th>Status</th>`,
    op.map((p,i)=>{
      const u=p.unrealized_pnl, st=u==null?'':(u>=0?'up':'down'), lbl=u==null?'no price':(u>=0?'▲ up':'▼ down');
      return `<tr class="clickrow" data-k="open" data-i="${i}"><td class="mkt">${mktCell(p.title, pmUrl(p))}</td><td>${esc(p.outcome)}</td>
        <td class="num">${p.entry_price}</td><td class="num">${p.current_price==null?'—':p.current_price}</td>
        <td class="num">${money(p.cost_usd)}</td><td class="num">${money(p.current_value)}</td>
        <td class="num ${signClass(u)}">${money(u)}</td>
        <td><span class="pill ${st||'low'}">${lbl}</span></td></tr>`;
    }).join(''),
    'No open positions yet.');

  // alerts
  const al = d.alerts;
  document.getElementById('c-al').textContent = al.length ? al.length : '';
  document.getElementById('alertsBody').innerHTML = wrapTable(
    `<th>Time (UTC)</th><th>Type</th><th class="mkt">Market</th><th>Pick</th><th class="num">Size</th>`,
    al.map(a=>`<tr><td style="color:var(--muted)">${esc((a.iso||'').replace('T',' ').replace('Z',''))}</td>
      <td><span class="pill ${esc(a.severity||'low')}">${esc(a.kind||'')}</span></td>
      <td class="mkt">${mktCell(a.title, pmUrl(a))}</td><td>${esc(a.outcome)}</td>
      <td class="num">${money(a.notional_usd||0)}</td></tr>`).join(''),
    'No alerts logged yet.');

  // settled
  const stl = d.settled_positions;
  document.getElementById('c-st').textContent = stl.length ? stl.length : '';
  document.getElementById('settledBody').innerHTML = wrapTable(
    `<th class="mkt">Market</th><th>Pick</th><th>Result</th><th class="num">P&L</th>`,
    stl.map((p,i)=>`<tr class="clickrow" data-k="settled" data-i="${i}"><td class="mkt">${mktCell(p.title, pmUrl(p))}</td><td>${esc(p.outcome)}</td>
      <td><span class="pill ${esc(p.status)}">${esc(p.status)}</span></td>
      <td class="num ${signClass(p.pnl)}">${money(p.pnl)}</td></tr>`).join(''),
    'Nothing settled yet — markets need to resolve first.');

  document.getElementById('dot').classList.remove('off');
  document.getElementById('updated').textContent = 'live · updated ' + new Date().toLocaleTimeString();

  // If a position detail modal is open and the position has just left the open
  // set (settled or sold), re-render it once so the buy/sell controls disappear.
  // While it's still open we leave the modal alone to avoid disrupting the user.
  if(CURRENT && CURRENT.id && document.getElementById('overlay').classList.contains('show')){
    const stillOpen = (d.open_positions||[]).some(p=>p.id===CURRENT.id);
    const wasOpen = !CURRENT.status || CURRENT.status==='open';
    if(wasOpen && !stillOpen){
      const closed=(d.settled_positions||[]).find(p=>p.id===CURRENT.id);
      if(closed) openDetail(closed);
    }
  }
}

// ---------- position detail modal ----------
let CURRENT = null;  // the position being shown

document.addEventListener('click', e=>{
  const row = e.target.closest('tr.clickrow');
  if(row && !e.target.closest('a')){  // ignore clicks on the market link itself
    const arr = row.dataset.k==='open' ? (window.DATA?.open_positions) : (window.DATA?.settled_positions);
    const p = arr && arr[+row.dataset.i];
    if(p) openDetail(p);
  }
});
document.getElementById('dClose').addEventListener('click', closeDetail);
document.getElementById('overlay').addEventListener('click', e=>{ if(e.target.id==='overlay') closeDetail(); });
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDetail(); });
document.getElementById('dIv').addEventListener('click', e=>{
  const b=e.target.closest('.ivbtn'); if(!b||!CURRENT) return;
  document.querySelectorAll('#dIv .ivbtn').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  loadChart(CURRENT.asset, b.dataset.iv);
});

function openDetail(p){
  CURRENT = p;
  const url = pmUrl(p);
  document.getElementById('dTitle').innerHTML = mktCell(p.title, url);
  document.getElementById('dSub').textContent =
    (p.signal? p.signal.replace('_',' ')+' signal · ' : '') + 'pick: ' + (p.outcome||'');

  const u = (p.unrealized_pnl!=null) ? p.unrealized_pnl : p.pnl;
  const rows = [
    ['Bought', p.opened_iso||'—'],
    ['Entry price', p.entry_price],
    ['Price now', p.current_price!=null?p.current_price:'—'],
    ['Cost', money(p.cost_usd)],
    ['Value now', p.current_value!=null?money(p.current_value):'—'],
    ['P&L', money(u)],
  ];
  if(p.status && p.status!=='open') rows.push(['Result', p.status.toUpperCase()]);
  if(p.settled_iso) rows.push(['Settled', p.settled_iso]);
  document.getElementById('dStats').innerHTML = rows.map(([l,v])=>{
    const cls = (l==='P&L')? signClass(u) : '';
    return `<div class="mstat"><div class="l">${l}</div><div class="v ${cls}">${v}</div></div>`;
  }).join('');

  // buy/sell controls (open positions only) — PAPER money
  const isOpen = !p.status || p.status==='open';
  const act = document.getElementById('dActions');
  if(isOpen){
    act.innerHTML = `<div class="msec">Manage position <span class="papertag">PAPER</span></div>
      <div class="actions">
        <input id="buyAmt" type="number" min="1" step="1" placeholder="$ amount">
        <button class="actbtn buy" id="buyBtn">Buy more</button>
        <select id="sellFrac">
          <option value="1">Sell 100%</option><option value="0.5">Sell 50%</option><option value="0.25">Sell 25%</option>
        </select>
        <button class="actbtn sell" id="sellBtn">Sell</button>
      </div>
      <div class="actmsg" id="actMsg">Orders apply on the bot's next cycle (~15s) at the live price.</div>`;
    document.getElementById('buyBtn').onclick = ()=>sendOrder('buy', {usd: parseFloat(document.getElementById('buyAmt').value||'0')});
    document.getElementById('sellBtn').onclick = ()=>sendOrder('sell', {fraction: parseFloat(document.getElementById('sellFrac').value||'1')});
  } else {
    act.innerHTML = '';
  }

  // wallets with profile links (upgraded to /@handle async)
  const ws = p.wallets||[];
  document.getElementById('dWallets').innerHTML = ws.length ? ws.map((w,i)=>
    `<div class="wallet"><code>${esc(w)}</code>
      <a id="wlink${i}" data-w="${esc(w)}" href="https://polymarket.com/profile/${esc(w)}" target="_blank" rel="noopener">view trader ↗</a></div>`
  ).join('') : '<div class="empty">Wallet info wasn\'t recorded for this older position.</div>';
  ws.forEach((w,i)=>upgradeWalletLink(w, 'wlink'+i));

  document.getElementById('overlay').classList.add('show');
  // reset interval to 1D and load
  document.querySelectorAll('#dIv .ivbtn').forEach(x=>x.classList.toggle('active', x.dataset.iv==='1d'));
  loadChart(p.asset, '1d');
}
function closeDetail(){ document.getElementById('overlay').classList.remove('show'); CURRENT=null; }

async function upgradeWalletLink(wallet, elId){
  try{
    const u='/api/walleturl?w='+encodeURIComponent(wallet)+(TOKEN?('&token='+encodeURIComponent(TOKEN)):'');
    const url=(await (await fetch(u,{cache:'no-store'})).json()).url;
    const el=document.getElementById(elId);
    // only apply if the element still belongs to this wallet (modal may have been reopened)
    if(el && url && el.dataset.w===wallet) el.href=url;
  }catch(e){}
}

async function sendOrder(action, payload){
  if(!CURRENT||!CURRENT.id){ return; }
  const msg=document.getElementById('actMsg');
  if(action==='buy' && (!payload.usd||payload.usd<=0)){ msg.className='actmsg err'; msg.textContent='Enter a $ amount to buy.'; return; }
  const verb = action==='buy' ? `buy $${payload.usd}` : `sell ${Math.round(payload.fraction*100)}%`;
  if(!confirm(`Confirm PAPER order: ${verb} of "${CURRENT.title}"? (fake money)`)) return;
  msg.className='actmsg'; msg.textContent='Queuing order…';
  document.getElementById('buyBtn').disabled=true; document.getElementById('sellBtn').disabled=true;
  try{
    const u='/api/order'+(TOKEN?('?token='+encodeURIComponent(TOKEN)):'');
    const body=Object.assign({action, position_id:CURRENT.id}, payload);
    const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j.ok){ msg.className='actmsg ok'; msg.textContent='✅ Order queued — it applies on the next bot cycle (~15s). Watch your balance update.'; }
    else { msg.className='actmsg err'; msg.textContent='⚠ '+(j.error||'failed'); }
  }catch(e){ msg.className='actmsg err'; msg.textContent='⚠ network error'; }
  finally{
    const bb=document.getElementById('buyBtn'), sb=document.getElementById('sellBtn');
    if(bb) bb.disabled=false; if(sb) sb.disabled=false;
  }
}

async function loadChart(asset, iv){
  const box = document.getElementById('dChart');
  box.innerHTML = '<div class="empty">Loading chart…</div>';
  if(!asset){ box.innerHTML='<div class="empty">No market data for this position.</div>'; return; }
  try{
    const u = '/api/history?m='+encodeURIComponent(asset)+'&iv='+iv+(TOKEN?('&token='+encodeURIComponent(TOKEN)):'');
    const r = await fetch(u, {cache:'no-store'});
    const pts = (await r.json()).history||[];
    drawChart(box, pts);
  }catch(e){ box.innerHTML='<div class="empty">Couldn\'t load chart.</div>'; }
}

function drawChart(box, pts){
  if(!pts.length){ box.innerHTML='<div class="empty">No price history yet.</div>'; return; }
  const W=680,H=240,pl=42,pr=14,pt=12,pb=26;
  const xs=pts.map(d=>d.t), ys=pts.map(d=>d.p);
  const tmin=Math.min(...xs), tmax=Math.max(...xs);
  let lo=Math.min(...ys), hi=Math.max(...ys); const pad=Math.max(0.02,(hi-lo)*0.15);
  lo=Math.max(0,lo-pad); hi=Math.min(1,hi+pad);
  const X=t=> pl+(W-pl-pr)*((t-tmin)/((tmax-tmin)||1));
  const Y=p=> pt+(H-pt-pb)*(1-((p-lo)/((hi-lo)||1)));
  const line=pts.map((d,i)=>(i?'L':'M')+X(d.t).toFixed(1)+' '+Y(d.p).toFixed(1)).join(' ');
  const area=line+` L ${X(tmax).toFixed(1)} ${H-pb} L ${X(tmin).toFixed(1)} ${H-pb} Z`;
  const up = ys[ys.length-1] >= ys[0];
  const col = up ? '#34d399' : '#f87171';
  // y gridlines
  let grid='';
  for(let k=0;k<=2;k++){ const val=lo+(hi-lo)*k/2; const y=Y(val);
    grid+=`<line x1="${pl}" y1="${y}" x2="${W-pr}" y2="${y}" stroke="#1e2a44"/>
           <text x="6" y="${y+4}" fill="#5d6e92" font-size="11">${val.toFixed(2)}</text>`; }
  // bought marker (vertical dashed line) if in range
  let mark='';
  if(CURRENT && CURRENT.opened_ts && CURRENT.opened_ts>=tmin && CURRENT.opened_ts<=tmax){
    const mx=X(CURRENT.opened_ts);
    mark=`<line x1="${mx}" y1="${pt}" x2="${mx}" y2="${H-pb}" stroke="#fbbf24" stroke-dasharray="4 3"/>
          <text x="${mx+4}" y="${pt+12}" fill="#fbbf24" font-size="10">bought</text>`;
  }
  box.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" id="csvg">
      <defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="${col}" stop-opacity="0.28"/>
        <stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient></defs>
      ${grid}
      <path d="${area}" fill="url(#g)"/>
      <path d="${line}" fill="none" stroke="${col}" stroke-width="2"/>
      ${mark}
      <line id="cx" x1="0" y1="${pt}" x2="0" y2="${H-pb}" stroke="#8b9bbd" stroke-dasharray="3 3" style="display:none"/>
      <circle id="cdot" r="3.5" fill="${col}" style="display:none"/>
      <rect x="${pl}" y="${pt}" width="${W-pl-pr}" height="${H-pt-pb}" fill="transparent" id="cover"/>
    </svg>
    <div class="ctip" id="ctip"></div>`;
  const svg=box.querySelector('#csvg'), cover=box.querySelector('#cover');
  const cx=box.querySelector('#cx'), cdot=box.querySelector('#cdot'), tip=box.querySelector('#ctip');
  cover.addEventListener('mousemove', ev=>{
    const r=svg.getBoundingClientRect(); const sx=(ev.clientX-r.left)*(W/r.width);
    const tt=tmin+(tmax-tmin)*((sx-pl)/((W-pl-pr)||1));
    let bi=0,bd=1e18; for(let i=0;i<pts.length;i++){const dd=Math.abs(pts[i].t-tt); if(dd<bd){bd=dd;bi=i;}}
    const d=pts[bi], px=X(d.t), py=Y(d.p);
    cx.setAttribute('x1',px); cx.setAttribute('x2',px); cx.style.display='';
    cdot.setAttribute('cx',px); cdot.setAttribute('cy',py); cdot.style.display='';
    const dt=new Date(d.t*1000);
    tip.style.display='block';
    tip.style.left=(px/W*r.width)+'px'; tip.style.top=(py/H*r.height)+'px';
    tip.innerHTML=`<b>${d.p.toFixed(3)}</b><br>${dt.toLocaleString()}`;
  });
  cover.addEventListener('mouseleave', ()=>{ cx.style.display='none'; cdot.style.display='none'; tip.style.display='none'; });
}

// ---------- suspects ----------
window.SUSPECTS = null;
window.SENRICH = {};   // wallet -> enriched data
let SUS_CAT = 'biggest';
const ENRICH_CAP = 40; // how many to enrich for richest/profit/winrate

async function loadSuspects(force){
  if(window.SUSPECTS && !force) { renderSuspects(SUS_CAT); return; }
  const box = document.getElementById('suspectsList');
  box.innerHTML = '<div class="empty">Loading suspects…</div>';
  try{
    const u='/api/suspects'+(TOKEN?('?token='+encodeURIComponent(TOKEN)):'');
    window.SUSPECTS = (await (await fetch(u,{cache:'no-store'})).json()).suspects||[];
    document.getElementById('c-sus').textContent = window.SUSPECTS.length||'';
    renderSuspects(SUS_CAT);
  }catch(e){ box.innerHTML='<div class="empty">Couldn\'t load suspects.</div>'; }
}

async function enrichTop(n){
  const list = (window.SUSPECTS||[]).slice(0, n);
  await Promise.all(list.map(async s=>{
    if(window.SENRICH[s.wallet]) return;
    try{
      const u='/api/suspect?w='+encodeURIComponent(s.wallet)+(TOKEN?('&token='+encodeURIComponent(TOKEN)):'');
      window.SENRICH[s.wallet] = await (await fetch(u,{cache:'no-store'})).json();
    }catch(e){ window.SENRICH[s.wallet] = {}; }
  }));
}

document.getElementById('suspectCats').addEventListener('click', async e=>{
  const b=e.target.closest('.ivbtn'); if(!b) return;
  document.querySelectorAll('#suspectCats .ivbtn').forEach(x=>x.classList.remove('active'));
  b.classList.add('active'); SUS_CAT=b.dataset.cat;
  if(['richest','profit','winrate'].includes(SUS_CAT)){
    document.getElementById('suspectsList').innerHTML='<div class="empty">Loading live Polymarket stats… (first time can take a few seconds)</div>';
    await enrichTop(ENRICH_CAP);
  }
  renderSuspects(SUS_CAT);
});

function renderSuspects(cat){
  const box=document.getElementById('suspectsList');
  let list=(window.SUSPECTS||[]).slice();
  if(!list.length){ box.innerHTML='<div class="empty">No suspects yet — the bot logs whales as it flags them.</div>'; return; }
  const enr=w=>window.SENRICH[w]||{};
  let metric;
  const showReasons = (cat==='suspicious');
  if(cat==='suspicious'){
    list = list.filter(s=>(s.suspicion||0) >= 2)
               .sort((a,b)=> (b.suspicion-a.suspicion) || (b.flagged_usd-a.flagged_usd));
    if(!list.length){ box.innerHTML='<div class="empty">🎉 No wallets are <b>obviously</b> suspicious right now — needs 2+ red flags (repeat buys, big money, many markets, or bursts).</div>'; return; }
    metric=s=>'🚩 '+s.suspicion;
  }
  else if(cat==='biggest'){ list.sort((a,b)=>b.flagged_usd-a.flagged_usd); metric=s=>money(s.flagged_usd); }
  else if(cat==='heavy'){ list.sort((a,b)=>b.markets-a.markets); metric=s=>s.markets+' mkts'; }
  else if(cat==='active'){ list.sort((a,b)=>b.flags-a.flags); metric=s=>s.flags+'×'; }
  else if(cat==='richest'){ list=list.slice(0,ENRICH_CAP).sort((a,b)=>(enr(b.wallet).value||-1)-(enr(a.wallet).value||-1)); metric=s=>{const v=enr(s.wallet).value; return v==null?'—':money(v);}; }
  else if(cat==='profit'){ list=list.slice(0,ENRICH_CAP).sort((a,b)=>(enr(b.wallet).pnl_all??-1e18)-(enr(a.wallet).pnl_all??-1e18)); metric=s=>{const v=enr(s.wallet).pnl_all; return v==null?'—':money(v);}; }
  else if(cat==='winrate'){ list=list.slice(0,ENRICH_CAP).sort((a,b)=>(enr(b.wallet).win_rate??-1)-(enr(a.wallet).win_rate??-1)); metric=s=>{const v=enr(s.wallet).win_rate; return v==null?'—':(v*100).toFixed(0)+'%';}; }

  box.innerHTML = '<div class="suspects-grid">' + list.map(s=>{
    const e=enr(s.wallet);
    const hl = metric(s);
    const hlCls = (cat==='profit') ? signClass(e.pnl_all) : (cat==='suspicious'?'neg':'');
    const reasonsHtml = (showReasons && s.reasons && s.reasons.length)
      ? `<div class="reasons">${s.reasons.map(r=>`<div class="reason">⚠ ${esc(r)}</div>`).join('')}</div>` : '';
    return `<div class="suspect ${cat==='suspicious'?'flagged':''}" data-w="${esc(s.wallet)}">
      <div class="hl ${hlCls}">${hl}</div>
      <div class="av">${cat==='suspicious'?'🚩':'🕵️'}</div>
      <div class="nm">${esc(s.name)}</div>
      <div class="ad">${esc(s.wallet.slice(0,10))}…${esc(s.wallet.slice(-4))}</div>
      <div class="row"><span>Flagged</span><b>${money(s.flagged_usd)}</b></div>
      <div class="row"><span>Times flagged</span><b>${s.flags}</b></div>
      <div class="row"><span>Markets</span><b>${s.markets}</b></div>
      ${reasonsHtml}
    </div>`;
  }).join('') + '</div>';
}

document.getElementById('suspectsList').addEventListener('click', e=>{
  const c=e.target.closest('.suspect'); if(c) openSuspect(c.dataset.w);
});
document.getElementById('sClose').addEventListener('click', ()=>document.getElementById('soverlay').classList.remove('show'));
document.getElementById('soverlay').addEventListener('click', e=>{ if(e.target.id==='soverlay') e.currentTarget.classList.remove('show'); });

async function openSuspect(wallet){
  const base=(window.SUSPECTS||[]).find(s=>s.wallet===wallet)||{wallet,name:_fallbackName(wallet)};
  document.getElementById('sTitle').textContent = base.name;
  document.getElementById('sSub').textContent = wallet;
  document.getElementById('sProfile').href = 'https://polymarket.com/profile/'+wallet;
  document.getElementById('sDesc').textContent = 'Loading their Polymarket dossier…';
  document.getElementById('sStats').innerHTML=''; document.getElementById('sPnl').innerHTML=''; document.getElementById('sOurs').innerHTML='';
  const rz = (base.reasons||[]);
  document.getElementById('sReasons').innerHTML = rz.length
    ? `<div class="msec" style="color:#ff8ba0">🚩 Why this wallet looks suspicious</div>
       <div class="reasons" style="margin-bottom:14px">${rz.map(r=>`<div class="reason">⚠ ${esc(r)}</div>`).join('')}</div>` : '';
  document.getElementById('soverlay').classList.add('show');
  let e = window.SENRICH[wallet];
  if(!e){
    try{ const u='/api/suspect?w='+encodeURIComponent(wallet)+(TOKEN?('&token='+encodeURIComponent(TOKEN)):'');
      e = window.SENRICH[wallet] = await (await fetch(u,{cache:'no-store'})).json(); }catch(_){ e={}; }
  }
  // upgrade the profile button to the canonical /@handle link when known —
  // but only if this suspect is still the one on screen (avoid a stale async
  // write when the user quickly opened a different suspect).
  if(e && e.profile_url && document.getElementById('sSub').textContent === wallet)
    document.getElementById('sProfile').href = e.profile_url;
  const mstat=(l,v,cls)=>`<div class="mstat"><div class="l">${l}</div><div class="v ${cls||''}">${v}</div></div>`;
  // description
  const wr = e.win_rate!=null ? (e.win_rate*100).toFixed(0)+'% win rate' : 'an unknown win rate';
  const age = e.age_days!=null ? `has been trading on Polymarket for ${Math.round(e.age_days)} days` : 'has been trading for a while';
  const bal = e.value!=null ? `holds ${money(e.value)} on the platform` : 'has an unknown balance';
  const pl = e.pnl_all!=null ? `is ${e.pnl_all>=0?'up':'down'} ${money(Math.abs(e.pnl_all))} all-time` : 'has murky all-time numbers';
  document.getElementById('sDesc').innerHTML =
    `<b>${esc(base.name)}</b> ${age}, ${bal}, and ${pl} with ${wr}` +
    (e.markets_traded?` across ${e.markets_traded} markets`:'') + '. Our bot has flagged this wallet ' +
    `<b>${base.flags||0}</b> time(s) for a total of <b>${money(base.flagged_usd||0)}</b> in suspicious buys.`;
  document.getElementById('sStats').innerHTML =
    mstat('Money in wallet', e.value!=null?money(e.value):'—') +
    mstat('Win rate', e.win_rate!=null?(e.win_rate*100).toFixed(1)+'%':'—', '') +
    mstat('W / L', (e.wins!=null?e.wins:'?')+' / '+(e.losses!=null?e.losses:'?')) +
    mstat('On Polymarket', e.age_days!=null?Math.round(e.age_days)+' days':'—', '') +
    mstat('Since', e.first_seen||'—') +
    mstat('Markets traded', e.markets_traded!=null?e.markets_traded:'—');
  document.getElementById('sPnl').innerHTML =
    mstat('Today', e.pnl_1d!=null?money(e.pnl_1d):'—', signClass(e.pnl_1d)) +
    mstat('This week', e.pnl_7d!=null?money(e.pnl_7d):'—', signClass(e.pnl_7d)) +
    mstat('This month', e.pnl_30d!=null?money(e.pnl_30d):'—', signClass(e.pnl_30d)) +
    mstat('All-time', e.pnl_all!=null?money(e.pnl_all):'—', signClass(e.pnl_all));
  document.getElementById('sOurs').innerHTML =
    mstat('We flagged', money(base.flagged_usd||0)) +
    mstat('Times flagged', base.flags||0) +
    mstat('In markets', base.markets||0) +
    mstat('First seen by us', base.first_iso||'—');
}
function _fallbackName(w){ return 'Suspect '+(w?w.slice(0,6):''); }

async function tick(){
  try {
    const r = await fetch(api, {cache:'no-store'});
    if(!r.ok){ document.getElementById('updated').textContent='error '+r.status;
               document.getElementById('dot').classList.add('off');
               setTimeout(tick, 5000); return; }
    const d = await r.json();
    render(d);
    setTimeout(tick, (d.refresh_seconds||15)*1000);
  } catch(e){
    document.getElementById('updated').textContent='offline — retrying…';
    document.getElementById('dot').classList.add('off');
    setTimeout(tick, 5000);
  }
}
tick();
</script>
</body>
</html>
"""
