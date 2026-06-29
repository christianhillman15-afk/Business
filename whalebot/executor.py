"""Optional live order execution — 'follow the whale'.

This is gated behind ``follow.enabled`` and defaults to ``dry_run: true``, in
which case it only logs the order it *would* have placed. Real placement uses
the official ``py-clob-client`` package, which is imported lazily so the
detection/paper path has no heavy dependencies.

Safety rails:
  * a per-day USD spend cap (``follow.daily_max_usd``)
  * a max price (don't chase near-certain outcomes)
  * stake sizing with an absolute per-order cap
  * credentials only ever come from environment variables
"""

from __future__ import annotations

import logging
import time

from .config import FollowConfig
from .models import Signal
from .state import State

log = logging.getLogger("whalebot.executor")


class Executor:
    def __init__(self, cfg: FollowConfig, state: State, clob_api: str) -> None:
        self.cfg = cfg
        self.state = state
        self.clob_api = clob_api
        self._client = None  # lazy CLOB client

    # -- sizing ------------------------------------------------------------
    def _stake_usd(self, sig: Signal) -> float:
        if self.cfg.sizing.mode == "percent":
            usd = sig.notional_usd * (self.cfg.sizing.percent_of_whale / 100.0)
        else:
            usd = self.cfg.sizing.fixed_usd
        return min(usd, self.cfg.sizing.max_usd)

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    # -- main entry --------------------------------------------------------
    def maybe_follow(self, sig: Signal) -> bool:
        """Place (or simulate) a follow order for a signal. Returns True if acted."""
        if not self.cfg.enabled:
            return False
        if sig.kind not in self.cfg.trigger_signals:
            return False
        if sig.price <= 0 or sig.price > self.cfg.max_price:
            log.info("skip follow: price %.3f outside (0, %.2f]", sig.price, self.cfg.max_price)
            return False

        stake = self._stake_usd(sig)
        if stake <= 0:
            return False

        day = self._today()
        if self.state.follow_spent_today(day) + stake > self.cfg.daily_max_usd:
            log.warning(
                "skip follow: daily cap reached (spent $%.0f / $%.0f)",
                self.state.follow_spent_today(day),
                self.cfg.daily_max_usd,
            )
            return False

        shares = stake / sig.price

        if self.cfg.dry_run:
            log.warning(
                "[DRY-RUN] would BUY %.2f shares of '%s' (%s) @ %.3f = $%.2f",
                shares,
                sig.outcome,
                sig.title,
                sig.price,
                stake,
            )
            self.state.add_follow_spend(day, stake)
            return True

        ok = self._place_live_order(sig, shares)
        if ok:
            self.state.add_follow_spend(day, stake)
        return ok

    # -- live order via py-clob-client ------------------------------------
    def _get_client(self):
        if self._client is not None:
            return self._client
        import os

        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.constants import POLYGON  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "live follow requires 'py-clob-client' (pip install py-clob-client)"
            ) from exc

        key = os.environ.get(self.cfg.private_key_env)
        if not key:
            raise RuntimeError(f"{self.cfg.private_key_env} is not set")
        funder = os.environ.get(self.cfg.funder_env) or None

        client = ClobClient(
            self.clob_api,
            key=key,
            chain_id=self.cfg.chain_id,
            funder=funder,
            signature_type=2 if funder else 0,
        )
        # Derive/create API credentials needed to sign orders.
        client.set_api_creds(client.create_or_derive_api_creds())
        self._client = client
        return client

    def _place_live_order(self, sig: Signal, shares: float) -> bool:  # pragma: no cover
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY

            client = self._get_client()
            order = client.create_order(
                OrderArgs(
                    token_id=sig.asset,
                    price=round(sig.price, 3),
                    size=round(shares, 2),
                    side=BUY,
                )
            )
            otype = OrderType.FOK if self.cfg.order_type == "FOK" else OrderType.GTC
            resp = client.post_order(order, otype)
            log.warning("LIVE order placed: %s", resp)
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("live order failed: %s", exc)
            return False
