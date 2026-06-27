"""The main polling loop that wires everything together."""

from __future__ import annotations

import logging
import signal
import time

from .client import PolymarketClient
from .config import Config
from .detector import Detector
from .executor import Executor
from .models import Signal
from .notifier import Notifier
from .paper import PaperPortfolio
from .state import State

log = logging.getLogger("whalebot.daemon")


class WhaleBot:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client = PolymarketClient(
            data_api=cfg.polymarket.data_api,
            gamma_api=cfg.polymarket.gamma_api,
            clob_api=cfg.polymarket.clob_api,
        )
        self.state = State(cfg.state.path, cfg.state.dedup_ttl_minutes)
        self.detector = Detector(cfg.detection, cfg.filters)
        self.notifier = Notifier(cfg.notifications)
        self.executor = Executor(cfg.follow, self.state, cfg.polymarket.clob_api)
        self.paper = PaperPortfolio(cfg.paper, self.state.paper)
        self._running = False

    # -- lifecycle ---------------------------------------------------------
    def run(self) -> None:
        self._running = True
        self._install_signal_handlers()
        log.info(
            "whalebot started | poll=%.0fs large=$%.0f follow=%s(dry=%s) paper=%s($%.0f)",
            self.cfg.poll.interval_seconds,
            self.cfg.detection.large_trade_usd,
            self.cfg.follow.enabled,
            self.cfg.follow.dry_run,
            self.cfg.paper.enabled,
            self.cfg.paper.starting_balance,
        )
        try:
            while self._running:
                start = time.time()
                try:
                    self.tick()
                except Exception as exc:  # noqa: BLE001 - never let the loop die
                    log.exception("tick failed: %s", exc)
                elapsed = time.time() - start
                self._sleep(max(0.0, self.cfg.poll.interval_seconds - elapsed))
        finally:
            self._shutdown()

    def _install_signal_handlers(self) -> None:
        def handler(signum, _frame):
            log.info("received signal %s, shutting down…", signum)
            self._running = False

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass  # not in main thread (e.g. tests) — ignore

    def _sleep(self, seconds: float) -> None:
        # sleep in small slices so a signal stops us promptly
        end = time.time() + seconds
        while self._running and time.time() < end:
            time.sleep(min(0.5, end - time.time()))

    def _shutdown(self) -> None:
        self.state.paper = self.paper.to_blob()
        self.state.save()
        log.info("state saved. %s", self.paper.report())

    # -- one poll cycle ----------------------------------------------------
    def tick(self) -> None:
        trades = self.client.fetch_trades(
            limit=self.cfg.poll.trades_per_poll,
            taker_only=self.cfg.poll.taker_only,
        )
        new = []
        for tr in trades:
            if self.state.is_new(tr.dedup_key):
                self.state.mark_seen(tr.dedup_key, tr.timestamp)
                new.append(tr)

        if new:
            log.debug("processing %d new trades (of %d fetched)", len(new), len(trades))

        signals = self.detector.process(new)
        for sig in signals:
            self._handle_signal(sig)

        self._maybe_settle()

        # persist + housekeeping
        self.state.prune()
        self.state.paper = self.paper.to_blob()
        self.state.save()

    def _handle_signal(self, sig: Signal) -> None:
        self.notifier.send(sig)

        pos = self.paper.maybe_buy(sig)
        if pos is not None:
            log.info(
                "📝 paper-bought %s '%s' @ %.3f (%.0f shares, $%.0f) — cash $%.0f",
                pos.outcome,
                pos.title,
                pos.entry_price,
                pos.shares,
                pos.cost_usd,
                self.paper.cash,
            )

        # live/dry-run follow (independent of paper trading)
        self.executor.maybe_follow(sig)

    def _maybe_settle(self) -> None:
        if not self.cfg.paper.enabled:
            return
        interval = self.cfg.paper.settle_interval_minutes * 60.0
        now = time.time()
        if now - self.state.last_settle_ts < interval:
            return
        self.state.last_settle_ts = now
        settled = self.paper.settle(self.client.resolve_market)
        if settled:
            for p in settled:
                log.info(
                    "✅ settled %s '%s' → %s  PnL $%+.2f",
                    p.outcome,
                    p.title,
                    p.status.upper(),
                    p.pnl,
                )
            self.notifier.info(self.paper.report())
