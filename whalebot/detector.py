"""Whale-detection logic.

The detector consumes the stream of *new* trades each poll and emits
:class:`~whalebot.models.Signal` objects when activity looks like a whale is
positioning to move a price. It keeps rolling per-(market,outcome) windows in
memory so it can spot accumulation and coordinated buying across polls.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from .config import DetectionConfig, FiltersConfig
from .models import Signal, Trade


class Detector:
    def __init__(self, detection: DetectionConfig, filters: FiltersConfig) -> None:
        self.d = detection
        self.f = filters
        # key (condition_id, asset) -> recent trades within the longest window
        self._recent: dict[tuple[str, str], Deque[Trade]] = defaultdict(deque)
        # longest window we need to retain, in seconds
        self._retain = (
            max(
                self.d.accumulation.window_minutes,
                self.d.coordinated.window_minutes,
            )
            * 60.0
        )

    # -- public API --------------------------------------------------------
    def process(self, trades: list[Trade], now: float | None = None) -> list[Signal]:
        """Feed new trades, return any signals they trigger.

        ``trades`` should be the trades not seen before. Order does not matter;
        we sort by timestamp internally so window logic is stable.
        """
        now = now if now is not None else time.time()
        signals: list[Signal] = []

        for tr in sorted(trades, key=lambda t: t.timestamp):
            if not self._passes_filters(tr):
                continue

            key = (tr.condition_id, tr.asset)
            window = self._recent[key]
            window.append(tr)
            self._trim(window, now)

            signals.extend(self._check_trade(tr))
            signals.extend(self._check_accumulation(tr, window))
            signals.extend(self._check_coordinated(tr, window))

        self._gc(now)
        return signals

    # -- filters -----------------------------------------------------------
    def _passes_filters(self, tr: Trade) -> bool:
        if self.f.sides and tr.side not in self.f.sides:
            return False
        if self.f.condition_ids and tr.condition_id.lower() not in self.f.condition_ids:
            return False
        return True

    # -- individual signals ------------------------------------------------
    def _check_trade(self, tr: Trade) -> list[Signal]:
        out: list[Signal] = []

        # Whale watchlist: always alert on configured wallets above a small floor.
        if tr.wallet in set(self.d.watchlist.wallets) and tr.notional >= self.d.watchlist.min_usd:
            out.append(
                Signal(
                    kind="watchlist",
                    severity="high",
                    title=tr.title,
                    outcome=tr.outcome,
                    asset=tr.asset,
                    condition_id=tr.condition_id,
                    notional_usd=tr.notional,
                    price=tr.price,
                    message=f"watched wallet {tr.wallet[:10]}… bought {tr.size:,.0f} shares",
                    trades=[tr],
                    wallets=[tr.wallet],
                )
            )

        # Large single buy.
        if self.d.large_trade_usd > 0 and tr.notional >= self.d.large_trade_usd:
            if tr.price >= self.d.min_price:
                sev = "high" if tr.notional >= self.d.large_trade_usd * 2 else "medium"
                out.append(
                    Signal(
                        kind="large_trade",
                        severity=sev,
                        title=tr.title,
                        outcome=tr.outcome,
                        asset=tr.asset,
                        condition_id=tr.condition_id,
                        notional_usd=tr.notional,
                        price=tr.price,
                        message=(
                            f"single {tr.side} of ${tr.notional:,.0f} "
                            f"({tr.size:,.0f} shares @ {tr.price:.3f})"
                        ),
                        trades=[tr],
                        wallets=[tr.wallet],
                    )
                )
        return out

    def _check_accumulation(self, tr: Trade, window: Deque[Trade]) -> list[Signal]:
        cfg = self.d.accumulation
        if not cfg.enabled:
            return []
        cutoff = tr.timestamp - cfg.window_minutes * 60.0
        same = [
            t
            for t in window
            if t.wallet == tr.wallet and t.outcome == tr.outcome and t.timestamp >= cutoff
        ]
        total = sum(t.notional for t in same)
        if len(same) >= cfg.min_trades and total >= cfg.min_total_usd:
            return [
                Signal(
                    kind="accumulation",
                    severity="high",
                    title=tr.title,
                    outcome=tr.outcome,
                    asset=tr.asset,
                    condition_id=tr.condition_id,
                    notional_usd=total,
                    price=tr.price,
                    message=(
                        f"wallet {tr.wallet[:10]}… accumulated ${total:,.0f} over "
                        f"{len(same)} buys in {cfg.window_minutes:.0f}m"
                    ),
                    trades=same,
                    wallets=[tr.wallet],
                )
            ]
        return []

    def _check_coordinated(self, tr: Trade, window: Deque[Trade]) -> list[Signal]:
        cfg = self.d.coordinated
        if not cfg.enabled:
            return []
        cutoff = tr.timestamp - cfg.window_minutes * 60.0
        same = [t for t in window if t.outcome == tr.outcome and t.timestamp >= cutoff]
        wallets = {t.wallet for t in same}
        total = sum(t.notional for t in same)
        if len(wallets) >= cfg.min_wallets and total >= cfg.min_total_usd:
            return [
                Signal(
                    kind="coordinated",
                    severity="high",
                    title=tr.title,
                    outcome=tr.outcome,
                    asset=tr.asset,
                    condition_id=tr.condition_id,
                    notional_usd=total,
                    price=tr.price,
                    message=(
                        f"{len(wallets)} wallets bought ${total:,.0f} of "
                        f"'{tr.outcome}' in {cfg.window_minutes:.0f}m"
                    ),
                    trades=same,
                    wallets=sorted(wallets),
                )
            ]
        return []

    # -- window maintenance ------------------------------------------------
    def _trim(self, window: Deque[Trade], now: float) -> None:
        cutoff = now - self._retain
        while window and window[0].timestamp < cutoff:
            window.popleft()

    def _gc(self, now: float) -> None:
        empty = [k for k, w in self._recent.items() if not w]
        for k in empty:
            del self._recent[k]
