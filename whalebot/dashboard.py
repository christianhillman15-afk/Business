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
import time
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
    closed_pos = [p for p in positions if p.status in ("won", "lost")]

    def settled_dict(p):
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
                "title": p.title,
                "outcome": p.outcome,
                "signal": p.signal_kind,
                "entry_price": round(p.entry_price, 3),
                "current_price": round(price, 3) if price is not None else None,
                "shares": round(p.shares, 1),
                "cost_usd": round(p.cost_usd, 2),
                "current_value": round(cur_value, 2) if cur_value is not None else None,
                "unrealized_pnl": round(unreal, 2) if unreal is not None else None,
            }
        )

    stats = portfolio.stats()
    # Live equity = cash + current market value of open positions.
    stats["live_equity"] = round(stats["cash"] + live_value_total, 2)
    stats["unrealized_pnl"] = round(unrealized_total, 2)

    return {
        "stats": stats,
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
                self._send_json(build_snapshot(cfg, client))
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
  .mkt{ max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .pill{ padding:3px 9px; border-radius:999px; font-size:11px; font-weight:700; white-space:nowrap; }
  .pill.high{ background:var(--red-bg); color:var(--red); }
  .pill.medium{ background:#352a10; color:var(--amber); }
  .pill.low,.pill.watchlist{ background:#10233b; color:var(--blue); }
  .pill.won,.pill.up{ background:var(--green-bg); color:var(--green); }
  .pill.lost,.pill.down{ background:var(--red-bg); color:var(--red); }
  .empty{ color:var(--dim); padding:34px 16px; text-align:center; font-style:italic; }
  footer{ text-align:center; color:var(--dim); font-size:12px; padding:28px 16px 8px; }
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
    <button class="tab" data-tab="alerts">Alerts<span class="count" id="c-al"></span></button>
    <button class="tab" data-tab="settled">Settled<span class="count" id="c-st"></span></button>
  </div>

  <div class="panel active" id="overview"><div class="cards" id="cards"></div></div>
  <div class="panel" id="positions"><div class="tablecard" id="open"></div></div>
  <div class="panel" id="alerts"><div class="tablecard" id="alertsBody"></div></div>
  <div class="panel" id="settled"><div class="tablecard" id="settledBody"></div></div>
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
});

function render(d){
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

  // current positions
  const op = d.open_positions;
  document.getElementById('c-pos').textContent = op.length ? op.length : '';
  document.getElementById('open').innerHTML = wrapTable(
    `<th class="mkt">Market</th><th>Pick</th><th class="num">Entry</th><th class="num">Now</th>
     <th class="num">Cost</th><th class="num">Value</th><th class="num">P&L</th><th>Status</th>`,
    op.map(p=>{
      const u=p.unrealized_pnl, st=u==null?'':(u>=0?'up':'down'), lbl=u==null?'no price':(u>=0?'▲ up':'▼ down');
      return `<tr><td class="mkt" title="${esc(p.title)}">${esc(p.title)}</td><td>${esc(p.outcome)}</td>
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
      <td class="mkt" title="${esc(a.title)}">${esc(a.title)}</td><td>${esc(a.outcome)}</td>
      <td class="num">${money(a.notional_usd||0)}</td></tr>`).join(''),
    'No alerts logged yet.');

  // settled
  const stl = d.settled_positions;
  document.getElementById('c-st').textContent = stl.length ? stl.length : '';
  document.getElementById('settledBody').innerHTML = wrapTable(
    `<th class="mkt">Market</th><th>Pick</th><th>Result</th><th class="num">P&L</th>`,
    stl.map(p=>`<tr><td class="mkt" title="${esc(p.title)}">${esc(p.title)}</td><td>${esc(p.outcome)}</td>
      <td><span class="pill ${esc(p.status)}">${esc(p.status)}</span></td>
      <td class="num ${signClass(p.pnl)}">${money(p.pnl)}</td></tr>`).join(''),
    'Nothing settled yet — markets need to resolve first.');

  document.getElementById('dot').classList.remove('off');
  document.getElementById('updated').textContent = 'live · updated ' + new Date().toLocaleTimeString();
}

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
