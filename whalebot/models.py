"""Data models for the whale bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Trade:
    """A single trade pulled from the Polymarket Data API ``/trades`` feed.

    The feed reports ``size`` in shares and ``price`` per share, so the USDC
    notional of the trade is ``size * price``.
    """

    wallet: str
    side: str  # "BUY" or "SELL"
    asset: str  # outcome token id
    condition_id: str
    size: float  # number of shares
    price: float  # price per share, 0..1
    timestamp: int  # unix seconds
    title: str
    slug: str
    outcome: str
    outcome_index: int
    tx_hash: str
    pseudonym: str = ""
    event_slug: str = ""

    @property
    def notional(self) -> float:
        """USDC value of the trade."""
        return self.size * self.price

    @property
    def dedup_key(self) -> str:
        """Stable identity for a trade leg (a tx can settle multiple legs)."""
        return f"{self.tx_hash}:{self.asset}:{self.wallet}:{self.size}:{self.price}"

    @property
    def when(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "Trade":
        """Build a Trade from a raw Data API record, tolerating missing fields."""
        return cls(
            wallet=str(raw.get("proxyWallet", "")).lower(),
            side=str(raw.get("side", "")).upper(),
            asset=str(raw.get("asset", "")),
            condition_id=str(raw.get("conditionId", "")),
            size=float(raw.get("size", 0) or 0),
            price=float(raw.get("price", 0) or 0),
            timestamp=int(raw.get("timestamp", 0) or 0),
            title=str(raw.get("title", "")),
            slug=str(raw.get("slug", "")),
            outcome=str(raw.get("outcome", "")),
            outcome_index=int(raw.get("outcomeIndex", 0) or 0),
            tx_hash=str(raw.get("transactionHash", "")),
            pseudonym=str(raw.get("pseudonym", "")),
            event_slug=str(raw.get("eventSlug", "")),
        )


@dataclass
class Signal:
    """An alert emitted by the detector when activity looks suspicious."""

    kind: str  # e.g. "large_trade", "accumulation", "coordinated", "watchlist"
    severity: str  # "low" | "medium" | "high"
    title: str  # market title
    outcome: str
    asset: str
    condition_id: str
    notional_usd: float
    price: float
    message: str
    slug: str = ""
    event_slug: str = ""
    trades: list[Trade] = field(default_factory=list)
    wallets: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.kind} :: {self.title} -> {self.outcome} "
            f"@ {self.price:.3f}  (${self.notional_usd:,.0f})  {self.message}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "outcome": self.outcome,
            "asset": self.asset,
            "condition_id": self.condition_id,
            "notional_usd": round(self.notional_usd, 2),
            "price": self.price,
            "message": self.message,
            "slug": self.slug,
            "event_slug": self.event_slug,
            "wallets": self.wallets,
            "tx_hashes": [t.tx_hash for t in self.trades],
        }
