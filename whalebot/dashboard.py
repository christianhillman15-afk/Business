"""A lightweight web dashboard for the whale bot.

Serves a single auto-refreshing web page (plus a small JSON API) so you can see
your paper account, open positions, settled results, and recent whale alerts in
a browser instead of the terminal. Uses only the Python standard library — no
extra installs.

Run with:  python -m whalebot dashboard
Then open: http://YOUR_SERVER_IP:8080
"""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import Config
from .paper import PaperPortfolio
from .state import State

log = logging.getLogger("whalebot.dashboard")


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


def build_snapshot(cfg: Config) -> dict:
    """Assemble the full dashboard payload from the bot's saved files."""
    # Reload state fresh each call so the dashboard reflects the live daemon.
    state = State(cfg.state.path, cfg.state.dedup_ttl_minutes)
    portfolio = PaperPortfolio(cfg.paper, state.paper)

    positions = sorted(
        portfolio.positions.values(), key=lambda p: p.opened_ts, reverse=True
    )
    open_pos = [p for p in positions if p.status == "open"]
    closed_pos = [p for p in positions if p.status in ("won", "lost")]

    def pos_dict(p):
        return {
            "title": p.title,
            "outcome": p.outcome,
            "signal": p.signal_kind,
            "entry_price": round(p.entry_price, 3),
            "shares": round(p.shares, 1),
            "cost_usd": round(p.cost_usd, 2),
            "status": p.status,
            "pnl": round(p.pnl, 2),
        }

    return {
        "stats": portfolio.stats(),
        "open_positions": [pos_dict(p) for p in open_pos],
        "settled_positions": [pos_dict(p) for p in closed_pos][:50],
        "alerts": _tail_jsonl(cfg.notifications.file.path, cfg.dashboard.recent_alerts),
        "refresh_seconds": cfg.dashboard.refresh_seconds,
    }


def _make_handler(cfg: Config):
    token = cfg.dashboard.token

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default noisy logging
            pass

        def _authorized(self, query: dict) -> bool:
            if not token:
                return True
            return query.get("token", [""])[0] == token

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if not self._authorized(query):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden: missing or wrong ?token=")
                return

            if parsed.path == "/api/data":
                self._send_json(build_snapshot(cfg))
            elif parsed.path in ("/", "/index.html"):
                self._send_html(PAGE)
            else:
                self.send_response(404)
                self.end_headers()

        def _send_json(self, payload: dict):
            body = json.dumps(payload).encode("utf-8")
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
<title>🐋 Whale Bot Dashboard</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, system-ui, Segoe UI, Roboto, sans-serif;
         background: #0b1220; color: #e6edf6; }
  header { padding: 18px 20px; background: #111a2e; border-bottom: 1px solid #1f2a44;
           display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
  header h1 { font-size: 20px; margin: 0; }
  .muted { color: #8aa0c0; font-size: 13px; }
  .wrap { padding: 20px; max-width: 1100px; margin: 0 auto; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap: 14px; }
  .card { background: #111a2e; border: 1px solid #1f2a44; border-radius: 12px; padding: 16px; }
  .card .label { font-size: 12px; color: #8aa0c0; text-transform: uppercase; letter-spacing: .04em; }
  .card .value { font-size: 26px; font-weight: 700; margin-top: 6px; }
  .pos { color: #41d18b; } .neg { color: #ff6b6b; }
  h2 { font-size: 15px; color: #b9c7de; margin: 28px 0 10px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid #1b263f; }
  th { color: #8aa0c0; font-weight: 600; }
  tr:hover td { background: #0f1a30; }
  .pill { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
  .pill.high { background: #4a1020; color: #ff8ba0; }
  .pill.medium { background: #3a2c10; color: #ffd27a; }
  .pill.low { background: #16324a; color: #8fd0ff; }
  .pill.won { background: #10331f; color: #5fe39b; }
  .pill.lost { background: #3a1620; color: #ff8ba0; }
  .pill.open { background: #16324a; color: #8fd0ff; }
  .empty { color: #6b7f9e; padding: 14px 4px; font-style: italic; }
  footer { text-align: center; color: #54678a; font-size: 12px; padding: 24px; }
</style>
</head>
<body>
<header>
  <h1>🐋 Whale Bot Dashboard</h1>
  <div class="muted" id="updated">connecting…</div>
</header>
<div class="wrap">
  <div class="cards" id="cards"></div>

  <h2>Open paper positions</h2>
  <div id="open"></div>

  <h2>Recent whale alerts</h2>
  <div id="alerts"></div>

  <h2>Settled trades</h2>
  <div id="settled"></div>
</div>
<footer>Auto-refreshing · paper trading (fake money) · data from your Polymarket whale bot</footer>

<script>
const TOKEN = new URLSearchParams(location.search).get('token') || '';
const api = '/api/data' + (TOKEN ? ('?token=' + encodeURIComponent(TOKEN)) : '');

function money(n){ return '$' + Number(n).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
function signClass(n){ return n > 0 ? 'pos' : (n < 0 ? 'neg' : ''); }
function esc(s){ return String(s==null?'':s).replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function card(label, value, cls){
  return `<div class="card"><div class="label">${label}</div><div class="value ${cls||''}">${value}</div></div>`;
}

function render(d){
  const s = d.stats;
  const roiCls = signClass(s.roi);
  const pnlCls = signClass(s.realized_pnl);
  document.getElementById('cards').innerHTML =
    card('Win rate', (s.win_rate*100).toFixed(1) + '%') +
    card('Equity', money(s.equity), roiCls) +
    card('ROI', (s.roi*100>=0?'+':'') + (s.roi*100).toFixed(1) + '%', roiCls) +
    card('Cash', money(s.cash)) +
    card('Record', s.wins + 'W / ' + s.losses + 'L') +
    card('Open', s.open_positions) +
    card('Realized PnL', money(s.realized_pnl), pnlCls);

  // open positions
  const op = d.open_positions;
  document.getElementById('open').innerHTML = op.length ? `<table>
    <tr><th>Market</th><th>Pick</th><th>Signal</th><th>Entry</th><th>Cost</th></tr>
    ${op.map(p=>`<tr><td>${esc(p.title)}</td><td>${esc(p.outcome)}</td>
      <td>${esc(p.signal)}</td><td>${p.entry_price}</td><td>${money(p.cost_usd)}</td></tr>`).join('')}
  </table>` : '<div class="empty">No open positions yet.</div>';

  // alerts
  const al = d.alerts;
  document.getElementById('alerts').innerHTML = al.length ? `<table>
    <tr><th>Time (UTC)</th><th>Type</th><th>Market</th><th>Pick</th><th>Size</th></tr>
    ${al.map(a=>`<tr>
      <td class="muted">${esc((a.iso||'').replace('T',' ').replace('Z',''))}</td>
      <td><span class="pill ${esc(a.severity||'low')}">${esc(a.kind||'')}</span></td>
      <td>${esc(a.title)}</td><td>${esc(a.outcome)}</td>
      <td>${money(a.notional_usd||0)}</td></tr>`).join('')}
  </table>` : '<div class="empty">No alerts logged yet.</div>';

  // settled
  const st = d.settled_positions;
  document.getElementById('settled').innerHTML = st.length ? `<table>
    <tr><th>Market</th><th>Pick</th><th>Result</th><th>PnL</th></tr>
    ${st.map(p=>`<tr><td>${esc(p.title)}</td><td>${esc(p.outcome)}</td>
      <td><span class="pill ${esc(p.status)}">${esc(p.status)}</span></td>
      <td class="${signClass(p.pnl)}">${money(p.pnl)}</td></tr>`).join('')}
  </table>` : '<div class="empty">Nothing settled yet — markets need to resolve first.</div>';

  const now = new Date().toLocaleTimeString();
  document.getElementById('updated').textContent = 'updated ' + now;
}

async function tick(){
  try {
    const r = await fetch(api, {cache:'no-store'});
    if(!r.ok){ document.getElementById('updated').textContent = 'error ' + r.status; return; }
    const d = await r.json();
    render(d);
    setTimeout(tick, (d.refresh_seconds||15)*1000);
  } catch(e){
    document.getElementById('updated').textContent = 'offline — retrying…';
    setTimeout(tick, 5000);
  }
}
tick();
</script>
</body>
</html>
"""
