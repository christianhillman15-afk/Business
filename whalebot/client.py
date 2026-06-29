"""HTTP client for the Polymarket public APIs (read-only)."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .models import Trade

log = logging.getLogger("whalebot.client")


class PolymarketClient:
    """Thin wrapper over the Polymarket Data and Gamma APIs.

    Only read-only endpoints are used here; order placement lives in
    :mod:`whalebot.executor` and uses the official CLOB client instead.
    """

    def __init__(
        self,
        data_api: str,
        gamma_api: str,
        clob_api: str,
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self.data_api = data_api.rstrip("/")
        self.gamma_api = gamma_api.rstrip("/")
        self.clob_api = clob_api.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")
        self.session.headers.setdefault("User-Agent", "polymarket-whale-bot/0.1")

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_trades(
        self,
        limit: int = 500,
        taker_only: bool = True,
        condition_id: str | None = None,
        user: str | None = None,
        offset: int = 0,
    ) -> list[Trade]:
        """Fetch the most recent trades from the Data API.

        The feed is returned newest-first. ``offset`` paginates further back.
        Network/parse errors are logged and swallowed (returns ``[]``) so a
        transient failure never kills the daemon.
        """
        params: dict[str, Any] = {"limit": limit, "takerOnly": str(taker_only).lower()}
        if offset:
            params["offset"] = offset
        if condition_id:
            params["market"] = condition_id
        if user:
            params["user"] = user

        try:
            raw = self._get(f"{self.data_api}/trades", params=params)
        except Exception as exc:  # noqa: BLE001 - resilience over precision here
            log.warning("fetch_trades failed: %s", exc)
            return []

        if not isinstance(raw, list):
            log.warning("fetch_trades: unexpected payload type %s", type(raw).__name__)
            return []

        trades: list[Trade] = []
        for rec in raw:
            try:
                trades.append(Trade.from_api(rec))
            except Exception as exc:  # noqa: BLE001
                log.debug("skipping malformed trade record: %s", exc)
        return trades

    def fetch_midpoint(self, token_id: str) -> float | None:
        """Current mid-market price (0..1) for an outcome token, or None.

        Used to mark open paper positions to market. Returns None if the token
        has no live order book (e.g. the market has closed).
        """
        if not token_id:
            return None
        try:
            raw = self._get(f"{self.clob_api}/midpoint", params={"token_id": token_id})
        except Exception as exc:  # noqa: BLE001
            log.debug("fetch_midpoint failed for %s: %s", token_id, exc)
            return None
        if isinstance(raw, dict) and "mid" in raw:
            try:
                return float(raw["mid"])
            except (TypeError, ValueError):
                return None
        return None

    def fetch_user_name(self, addr: str) -> str:
        """Best-effort Polymarket username/handle for a wallet (from its trades).

        Returns the handle (e.g. 'phonesculptor') if the user set one, else ''.
        Polymarket's canonical profile URL is /@<handle>.
        """
        try:
            raw = self._get(
                f"{self.data_api}/trades", params={"user": addr, "limit": 1}
            )
        except Exception:  # noqa: BLE001
            return ""
        if isinstance(raw, list) and raw:
            return str(raw[0].get("name", "") or "")
        return ""

    def fetch_user_value(self, addr: str) -> float | None:
        """Current Polymarket portfolio value (USDC) for a wallet."""
        try:
            raw = self._get(f"{self.data_api}/value", params={"user": addr})
        except Exception:  # noqa: BLE001
            return None
        if isinstance(raw, list) and raw:
            try:
                return float(raw[0].get("value"))
            except (TypeError, ValueError):
                return None
        return None

    def fetch_user_profit(self, addr: str, window: str = "all") -> tuple[float | None, str]:
        """PnL for a wallet over a window (1d/7d/30d/all) via the leaderboard API.

        Returns (amount, pseudonym). pseudonym often ends in '-<ms>' which marks
        when the wallet first appeared on Polymarket.
        """
        url = "https://lb-api.polymarket.com/profit"
        try:
            resp = self.session.get(
                url, params={"window": window, "address": addr}, timeout=self.timeout
            )
            raw = resp.json()
        except Exception:  # noqa: BLE001
            return None, ""
        if isinstance(raw, list) and raw:
            try:
                return float(raw[0].get("amount")), str(raw[0].get("pseudonym", ""))
            except (TypeError, ValueError):
                return None, ""
        return None, ""

    def fetch_user_positions(self, addr: str, limit: int = 500) -> list[dict]:
        """A wallet's positions (incl. resolved/redeemable) for win-rate stats."""
        try:
            raw = self._get(
                f"{self.data_api}/positions", params={"user": addr, "limit": limit}
            )
        except Exception:  # noqa: BLE001
            return []
        return raw if isinstance(raw, list) else []

    def fetch_price_history(
        self, token_id: str, interval: str = "1d", fidelity: int = 60
    ) -> list[dict]:
        """Price history for an outcome token: list of {"t": unix, "p": price}.

        ``interval`` is one of 1h/6h/1d/1w/max; ``fidelity`` is the bucket size
        in minutes. Returns [] on any error so the dashboard degrades gracefully.
        """
        if not token_id:
            return []
        try:
            raw = self._get(
                f"{self.clob_api}/prices-history",
                params={"market": token_id, "interval": interval, "fidelity": fidelity},
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("fetch_price_history failed for %s: %s", token_id, exc)
            return []
        hist = raw.get("history") if isinstance(raw, dict) else None
        return hist if isinstance(hist, list) else []

    def fetch_market(
        self, condition_id: str, include_closed: bool = True
    ) -> dict[str, Any] | None:
        """Fetch market metadata from Gamma by condition id (best-effort).

        Gamma's ``/markets`` endpoint excludes closed markets by default, so we
        pass ``closed=true`` when we need resolved markets (the common case for
        settlement). The filter param is the snake_case ``condition_ids``.
        """
        params: dict[str, Any] = {"condition_ids": condition_id}
        if include_closed:
            params["closed"] = "true"
        try:
            raw = self._get(f"{self.gamma_api}/markets", params=params)
        except Exception as exc:  # noqa: BLE001
            log.debug("fetch_market failed for %s: %s", condition_id, exc)
            return None
        if isinstance(raw, list) and raw:
            return raw[0]
        return None

    def fetch_recent_closed_markets(self, limit: int = 40) -> list[dict]:
        """Recently-closed, high-volume markets (for backtesting on known outcomes)."""
        try:
            raw = self._get(
                f"{self.gamma_api}/markets",
                params={
                    "closed": "true",
                    "limit": limit,
                    "order": "volume",
                    "ascending": "false",
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("fetch_recent_closed_markets failed: %s", exc)
            return []
        return raw if isinstance(raw, list) else []

    def winner_from_market(self, market: dict) -> str | None:
        """Winning outcome name from a (closed) market dict, else None."""
        if not market or not market.get("closed"):
            return None
        outcomes = _parse_json_list(market.get("outcomes"))
        prices = _parse_json_list(market.get("outcomePrices"))
        if not outcomes or len(outcomes) != len(prices):
            return None
        for name, price in zip(outcomes, prices):
            try:
                if float(price) >= 0.99:
                    return str(name)
            except (TypeError, ValueError):
                continue
        return None

    def resolve_market(self, condition_id: str) -> str | None:
        """Return the winning outcome name for a resolved market, else ``None``.

        A market is considered resolved once Gamma marks it ``closed`` and one
        of its ``outcomePrices`` has settled to (approximately) 1. Both
        ``outcomes`` and ``outcomePrices`` come back as JSON-encoded strings.
        """
        market = self.fetch_market(condition_id)
        if not market:
            return None
        if not market.get("closed"):
            return None

        outcomes = _parse_json_list(market.get("outcomes"))
        prices = _parse_json_list(market.get("outcomePrices"))
        if not outcomes or len(outcomes) != len(prices):
            return None

        for name, price in zip(outcomes, prices):
            try:
                if float(price) >= 0.99:
                    return str(name)
            except (TypeError, ValueError):
                continue
        return None


def _parse_json_list(value: Any) -> list:
    """Gamma encodes list fields as JSON strings; tolerate raw lists too."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []
