"""Paper-trading portfolio — the fake-money 'demo account'.

When the detector flags a market, the portfolio simulates buying the flagged
outcome at the trade's price using a fixed fake stake, deducting from a starting
balance (default $1000). Open positions are later settled against the real
market resolution pulled from the Gamma API:

* if the bought outcome won  -> each share pays out $1
* if it lost                 -> the position is worth $0

From the settled history we compute a running **win rate** and PnL so you can
judge whether the whale signals are actually predictive before risking real
money.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .config import PaperConfig
from .models import Signal

log = logging.getLogger("whalebot.paper")


@dataclass
class PaperPosition:
    id: str  # condition_id:asset (one position per market outcome)
    condition_id: str
    asset: str
    title: str
    outcome: str
    signal_kind: str
    entry_price: float
    shares: float
    cost_usd: float
    opened_ts: float
    status: str = "open"  # open | won | lost
    settled_ts: float | None = None
    payout_usd: float = 0.0
    slug: str = ""  # market slug, for linking to polymarket.com
    event_slug: str = ""

    @property
    def pnl(self) -> float:
        if self.status == "open":
            return 0.0
        return self.payout_usd - self.cost_usd


class PaperPortfolio:
    def __init__(self, cfg: PaperConfig, blob: dict[str, Any] | None = None) -> None:
        self.cfg = cfg
        self.cash: float = cfg.starting_balance
        self.positions: dict[str, PaperPosition] = {}
        if blob:
            self._restore(blob)

    # -- (de)serialisation -------------------------------------------------
    def _restore(self, blob: dict[str, Any]) -> None:
        self.cash = float(blob.get("cash", self.cfg.starting_balance))
        for pid, p in (blob.get("positions") or {}).items():
            try:
                self.positions[pid] = PaperPosition(**p)
            except Exception as exc:  # noqa: BLE001
                log.debug("skipping bad paper position %s: %s", pid, exc)

    def to_blob(self) -> dict[str, Any]:
        return {
            "cash": self.cash,
            "positions": {pid: asdict(p) for pid, p in self.positions.items()},
        }

    # -- buying ------------------------------------------------------------
    def maybe_buy(self, sig: Signal, now: float | None = None) -> PaperPosition | None:
        """Simulate a buy for a signal, respecting stake/exposure/price caps.

        Returns the position if a (possibly incremental) buy happened, else
        ``None`` (filtered out, capped, or insufficient cash).
        """
        now = now if now is not None else time.time()
        if not self.cfg.enabled:
            return None
        if sig.kind not in self.cfg.trigger_signals:
            return None
        if sig.price <= 0 or sig.price > self.cfg.max_price:
            return None

        pid = f"{sig.condition_id}:{sig.asset}"
        existing = self.positions.get(pid)

        # Determine how much we *want* to stake, capped by per-market exposure.
        already = existing.cost_usd if existing and existing.status == "open" else 0.0
        room = self.cfg.max_position_usd - already
        if room <= 0:
            return None
        stake = min(self.cfg.stake_usd, room, self.cash)
        if stake <= 0:
            return None

        shares = stake / sig.price
        self.cash -= stake

        if existing and existing.status == "open":
            # average into the existing position
            total_shares = existing.shares + shares
            total_cost = existing.cost_usd + stake
            existing.shares = total_shares
            existing.cost_usd = total_cost
            existing.entry_price = total_cost / total_shares
            self._append_ledger("add", existing, stake, now)
            return existing

        pos = PaperPosition(
            id=pid,
            condition_id=sig.condition_id,
            asset=sig.asset,
            title=sig.title,
            outcome=sig.outcome,
            signal_kind=sig.kind,
            entry_price=sig.price,
            shares=shares,
            cost_usd=stake,
            opened_ts=now,
            slug=sig.slug,
            event_slug=sig.event_slug,
        )
        self.positions[pid] = pos
        self._append_ledger("open", pos, stake, now)
        return pos

    # -- settlement --------------------------------------------------------
    def settle(self, resolver, now: float | None = None) -> list[PaperPosition]:
        """Settle open positions whose markets have resolved.

        ``resolver(condition_id) -> winning_outcome | None``. Returns the list
        of positions that were settled this call.
        """
        now = now if now is not None else time.time()
        settled: list[PaperPosition] = []
        for pos in self.positions.values():
            if pos.status != "open":
                continue
            winner = resolver(pos.condition_id)
            if winner is None:
                continue  # not resolved yet (or unknown)
            won = winner.strip().lower() == pos.outcome.strip().lower()
            pos.status = "won" if won else "lost"
            pos.payout_usd = pos.shares * 1.0 if won else 0.0
            pos.settled_ts = now
            self.cash += pos.payout_usd
            self._append_ledger("settle", pos, pos.payout_usd, now)
            settled.append(pos)
        return settled

    # -- reporting ---------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        closed = [p for p in self.positions.values() if p.status in ("won", "lost")]
        open_pos = [p for p in self.positions.values() if p.status == "open"]
        wins = sum(1 for p in closed if p.status == "won")
        realized = sum(p.pnl for p in closed)
        open_cost = sum(p.cost_usd for p in open_pos)
        equity = self.cash + open_cost  # open positions held at cost basis
        win_rate = (wins / len(closed)) if closed else 0.0
        roi = (equity - self.cfg.starting_balance) / self.cfg.starting_balance
        return {
            "starting_balance": self.cfg.starting_balance,
            "cash": round(self.cash, 2),
            "open_positions": len(open_pos),
            "open_cost_basis": round(open_cost, 2),
            "equity": round(equity, 2),
            "settled_trades": len(closed),
            "wins": wins,
            "losses": len(closed) - wins,
            "win_rate": round(win_rate, 4),
            "realized_pnl": round(realized, 2),
            "roi": round(roi, 4),
        }

    def report(self) -> str:
        s = self.stats()
        return (
            "─── Paper account ───\n"
            f"  Starting:   ${s['starting_balance']:,.2f}\n"
            f"  Cash:       ${s['cash']:,.2f}\n"
            f"  Open:       {s['open_positions']} positions (${s['open_cost_basis']:,.2f} cost)\n"
            f"  Equity:     ${s['equity']:,.2f}  (ROI {s['roi'] * 100:+.1f}%)\n"
            f"  Settled:    {s['settled_trades']}  →  {s['wins']}W / {s['losses']}L\n"
            f"  Win rate:   {s['win_rate'] * 100:.1f}%\n"
            f"  Realized PnL: ${s['realized_pnl']:,.2f}"
        )

    # -- ledger ------------------------------------------------------------
    def _append_ledger(self, action: str, pos: PaperPosition, amount: float, ts: float) -> None:
        if not self.cfg.ledger_path:
            return
        row = {
            "ts": ts,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
            "action": action,  # open | add | settle
            "id": pos.id,
            "title": pos.title,
            "outcome": pos.outcome,
            "signal": pos.signal_kind,
            "entry_price": round(pos.entry_price, 4),
            "shares": round(pos.shares, 2),
            "amount_usd": round(amount, 2),
            "status": pos.status,
            "pnl": round(pos.pnl, 2),
            "cash_after": round(self.cash, 2),
        }
        try:
            with open(self.cfg.ledger_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        except Exception as exc:  # noqa: BLE001
            log.warning("could not append to paper ledger: %s", exc)
