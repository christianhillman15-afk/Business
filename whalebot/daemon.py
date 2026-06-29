"""The main polling loop that wires everything together."""

from __future__ import annotations

import glob
import json
import logging
import math
import os
import signal
import time

from .client import PolymarketClient
from .config import Config
from .detector import Detector
from .executor import Executor
from .models import Signal
from .notifier import Notifier
from .paper import PaperPortfolio
from .quality import WhaleQuality
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
        self.quality = WhaleQuality(self.client, cfg.paper.smart_money)
        # (market, outcome, kind) -> last alert ts, for cooldown throttling
        self._alert_cooldown: dict[tuple, float] = {}
        self._last_summary_day: str = ""
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

        # Record flagged wallets ("suspects") — attribute each NEW trade once,
        # even if it appears in several signals this tick.
        new_keys = {t.dedup_key for t in new}
        attributed: dict[str, object] = {}
        for sig in signals:
            for tr in sig.trades:
                if tr.dedup_key in new_keys:
                    attributed[tr.dedup_key] = tr
        for tr in attributed.values():
            self.state.record_suspect(tr.wallet, tr.condition_id, tr.notional, tr.timestamp)

        self._process_commands()
        self._maybe_settle()
        self._maybe_daily_summary()

        # persist + housekeeping
        self.state.prune()
        self.state.paper = self.paper.to_blob()
        self.state.save()

    def _handle_signal(self, sig: Signal) -> None:
        # Throttle repeat alerts for the same market/outcome/signal.
        if self._alert_suppressed(sig):
            return
        self.notifier.send(sig)

        # Smart-money gate: only follow whales with a track record, don't chase.
        ok, reason = self.quality.passes(sig)
        if not ok:
            log.info("⏭️  skip '%s' (%s): %s", sig.outcome, sig.title, reason)
            return

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

    def _alert_suppressed(self, sig: Signal) -> bool:
        cooldown = self.cfg.detection.alert_cooldown_minutes * 60.0
        if cooldown <= 0:
            return False
        key = (sig.condition_id, sig.outcome, sig.kind)
        now = time.time()
        last = self._alert_cooldown.get(key, 0.0)
        if now - last < cooldown:
            return True
        self._alert_cooldown[key] = now
        # opportunistic cleanup so the dict can't grow unbounded
        if len(self._alert_cooldown) > 5000:
            cutoff = now - cooldown
            self._alert_cooldown = {
                k: t for k, t in self._alert_cooldown.items() if t >= cutoff
            }
        return False

    def _process_commands(self) -> None:
        """Apply manual buy/sell commands the dashboard dropped in commands_dir.

        The bot is the single writer of the paper book, so all mutations funnel
        through here. Ordering is apply -> persist -> delete (with an idempotency
        set) so a crash can never lose a command nor double-apply one:
          * crash before save  -> files remain, ids not persisted -> re-applied
          * crash after save   -> ids persisted -> re-read commands are skipped
        """
        cdir = self.cfg.paper.commands_dir
        if not cdir or not os.path.isdir(cdir):
            return
        to_delete: list[str] = []
        applied_any = False
        for path in sorted(glob.glob(os.path.join(cdir, "*.json"))):
            cid = os.path.basename(path)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    cmd = json.load(fh)
            except Exception as exc:  # noqa: BLE001
                log.warning("bad command file %s: %s", path, exc)
                to_delete.append(path)
                continue
            if self.state.command_applied(cid):
                to_delete.append(path)  # already applied in a prior tick
                continue
            try:
                self._apply_command(cmd)
            except Exception as exc:  # noqa: BLE001
                log.warning("command failed (%s): %s", cmd, exc)
            self.state.mark_command_applied(cid)
            applied_any = True
            to_delete.append(path)

        if applied_any:
            # Persist the mutated book + idempotency set BEFORE deleting files.
            self.state.paper = self.paper.to_blob()
            self.state.save()
        for path in to_delete:
            self._rm(path)

    def _apply_command(self, cmd: dict) -> None:
        action = str(cmd.get("action", "")).lower()
        pid = str(cmd.get("position_id", ""))
        if action not in ("buy", "sell"):
            log.warning("unknown command action: %s", action)
            return
        pos = self.paper.positions.get(pid)
        if not pos:
            log.warning("command for unknown position %s", pid)
            return
        price = self.client.fetch_midpoint(pos.asset)
        if action == "buy":
            if price is None or not math.isfinite(price) or price <= 0:
                log.warning("no usable price for BUY %s; dropped", pid)
                return
            usd = self._finite(cmd.get("usd"))
            if usd is None or usd <= 0:
                log.warning("invalid BUY amount for %s; dropped", pid)
                return
            r = self.paper.manual_buy(pid, usd, price)
            if r:
                log.warning("🟢 manual BUY $%.2f of '%s' @ %.3f", usd, r.title, price)
            else:
                log.warning("BUY of %s had no effect (insufficient cash / not open)", pid)
        else:  # sell
            if price is None or not math.isfinite(price) or price < 0:
                log.warning("no usable price for SELL %s; dropped", pid)
                return
            frac = self._finite(cmd.get("fraction"))
            if frac is None:
                frac = 1.0
            r = self.paper.manual_sell(pid, frac, price)
            if r:
                log.warning("🔴 manual SELL %.0f%% of '%s' @ %.3f → PnL $%+.2f",
                            max(0.0, min(1.0, frac)) * 100, r.title, price, r.pnl)
            else:
                log.warning("SELL of %s had no effect (not open?)", pid)

    @staticmethod
    def _finite(value) -> float | None:
        """Parse a number, rejecting None/NaN/Infinity."""
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    @staticmethod
    def _rm(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    def _maybe_daily_summary(self) -> None:
        cfg = self.cfg.notifications.daily_summary
        if not cfg.enabled:
            return
        tm = time.gmtime()
        day = time.strftime("%Y-%m-%d", tm)
        if tm.tm_hour < cfg.hour_utc or self._last_summary_day == day:
            return
        self._last_summary_day = day
        s = self.paper.stats()
        top = sorted(
            self.state.suspects.items(),
            key=lambda kv: kv[1].get("usd", 0.0),
            reverse=True,
        )[:3]
        whales = ", ".join(f"{w[:8]}… (${r.get('usd', 0):,.0f})" for w, r in top) or "none yet"
        msg = (
            f"📅 Whale Bot daily — {day}\n"
            f"Equity ${s['equity']:,.2f} (ROI {s['roi'] * 100:+.1f}%) · "
            f"win rate {s['win_rate'] * 100:.0f}% ({s['wins']}W/{s['losses']}L) · "
            f"realized ${s['realized_pnl']:,.2f}\n"
            f"Open {s['open_positions']} · cash ${s['cash']:,.2f}\n"
            f"Top whales: {whales}"
        )
        self.notifier.info(msg)

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
