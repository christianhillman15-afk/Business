"""Smart-money gating: only follow whales with a track record, don't chase.

Whale quality (all-time PnL, approximate win rate) is pulled from Polymarket and
cached per wallet so the hot path doesn't hammer the API. The gate fails OPEN:
if we can't fetch a whale's stats, we allow the trade rather than silently
halt trading on a transient API error.
"""

from __future__ import annotations

import logging
import time

from .client import PolymarketClient
from .config import SmartMoneyConfig
from .models import Signal

log = logging.getLogger("whalebot.quality")


class WhaleQuality:
    def __init__(self, client: PolymarketClient, cfg: SmartMoneyConfig) -> None:
        self.client = client
        self.cfg = cfg
        self._cache: dict[str, tuple[dict, float]] = {}

    def stats(self, wallet: str) -> dict | None:
        """Cached {pnl_all, win_rate} for a wallet, or None if unavailable."""
        now = time.time()
        hit = self._cache.get(wallet)
        if hit and (now - hit[1]) < self.cfg.cache_ttl_minutes * 60.0:
            return hit[0]
        pnl_all, _ = self.client.fetch_user_profit(wallet, "all")
        if pnl_all is None:
            return None  # don't cache failures; retry next time
        win_rate = None
        if self.cfg.min_win_rate > 0:
            positions = self.client.fetch_user_positions(wallet, limit=500)
            wins = losses = 0
            for p in positions:
                try:
                    cur = float(p.get("curPrice", -1))
                    if p.get("redeemable") or cur in (0.0, 1.0):
                        rp = float(p.get("realizedPnl", 0) or 0)
                        if rp > 0:
                            wins += 1
                        elif rp < 0:
                            losses += 1
                except (TypeError, ValueError):
                    continue
            if wins + losses:
                win_rate = wins / (wins + losses)
        data = {"pnl_all": pnl_all, "win_rate": win_rate}
        self._cache[wallet] = (data, now)
        return data

    def passes(self, sig: Signal) -> tuple[bool, str]:
        """Return (ok, reason). Decides whether to follow this signal."""
        if not self.cfg.enabled:
            return True, ""

        # Chase guard: skip if the live price already ran well past the entry.
        cur = self.client.fetch_midpoint(sig.asset)
        if cur is not None and sig.price > 0:
            slippage = (cur - sig.price) / sig.price
            if slippage > self.cfg.max_chase_slippage:
                return False, f"price already ran {slippage * 100:.0f}% past entry"

        # Smart-money: the triggering whale must have a track record.
        wallet = sig.wallets[0] if sig.wallets else ""
        if not wallet:
            return True, ""  # nothing to judge -> allow
        st = self.stats(wallet)
        if st is None:
            return True, "whale stats unavailable (allowed)"  # fail open
        if st["pnl_all"] < self.cfg.min_all_time_pnl:
            return False, f"whale all-time PnL ${st['pnl_all']:,.0f} below cutoff"
        if (
            self.cfg.min_win_rate > 0
            and st["win_rate"] is not None
            and st["win_rate"] < self.cfg.min_win_rate
        ):
            return False, f"whale win rate {st['win_rate'] * 100:.0f}% below cutoff"
        return True, ""
