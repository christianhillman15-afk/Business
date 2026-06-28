"""Persistent state: trade de-duplication, follow-spend tracking, paper book.

Everything the daemon needs to survive a restart lives in one JSON file so we
never re-alert on trades we already processed and never lose the paper ledger.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

log = logging.getLogger("whalebot.state")


class State:
    def __init__(self, path: str, dedup_ttl_minutes: float = 120.0) -> None:
        self.path = path
        self.dedup_ttl = dedup_ttl_minutes * 60.0
        # dedup_key -> first-seen unix ts
        self.seen: dict[str, float] = {}
        # YYYY-MM-DD -> usd spent following trades (live executor safety cap)
        self.follow_spend: dict[str, float] = {}
        # opaque blob owned by the paper portfolio
        self.paper: dict[str, Any] = {}
        # wallet (lowercased) -> aggregated "suspect" stats we've observed
        self.suspects: dict[str, dict] = {}
        # ids of manual buy/sell commands already applied (idempotency)
        self.applied_commands: list[str] = []
        self.last_settle_ts: float = 0.0
        self._load()

    # -- persistence -------------------------------------------------------
    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.seen = {k: float(v) for k, v in data.get("seen", {}).items()}
            self.follow_spend = {k: float(v) for k, v in data.get("follow_spend", {}).items()}
            self.paper = data.get("paper", {}) or {}
            self.suspects = data.get("suspects", {}) or {}
            self.applied_commands = list(data.get("applied_commands", []) or [])
            self.last_settle_ts = float(data.get("last_settle_ts", 0.0))
        except Exception as exc:  # noqa: BLE001
            log.warning("could not load state from %s (%s); starting fresh", self.path, exc)

    def save(self) -> None:
        tmp = f"{self.path}.tmp"
        data = {
            "seen": self.seen,
            "follow_spend": self.follow_spend,
            "paper": self.paper,
            "suspects": self.suspects,
            "applied_commands": self.applied_commands[-1000:],
            "last_settle_ts": self.last_settle_ts,
        }
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, self.path)  # atomic
        except Exception as exc:  # noqa: BLE001
            log.warning("could not save state to %s: %s", self.path, exc)

    # -- dedup -------------------------------------------------------------
    def is_new(self, key: str) -> bool:
        return key not in self.seen

    def mark_seen(self, key: str, ts: float | None = None) -> None:
        self.seen[key] = ts if ts is not None else time.time()

    def prune(self, now: float | None = None) -> int:
        """Drop dedup keys older than the TTL. Returns number removed."""
        now = now if now is not None else time.time()
        cutoff = now - self.dedup_ttl
        stale = [k for k, t in self.seen.items() if t < cutoff]
        for k in stale:
            del self.seen[k]
        return len(stale)

    # -- suspects (flagged wallets) ----------------------------------------
    def record_suspect(self, wallet: str, condition_id: str, usd: float, ts: float) -> None:
        """Accumulate observed stats for a flagged wallet (call once per trade)."""
        if not wallet:
            return
        rec = self.suspects.get(wallet)
        if rec is None:
            rec = {"flags": 0, "usd": 0.0, "markets": [], "first_ts": ts, "last_ts": ts}
            self.suspects[wallet] = rec
        rec["flags"] += 1
        rec["usd"] = round(rec.get("usd", 0.0) + usd, 2)
        if condition_id and condition_id not in rec["markets"] and len(rec["markets"]) < 100:
            rec["markets"].append(condition_id)
        rec["first_ts"] = min(rec.get("first_ts", ts), ts)
        rec["last_ts"] = max(rec.get("last_ts", ts), ts)

    # -- manual command idempotency ----------------------------------------
    def command_applied(self, cmd_id: str) -> bool:
        return cmd_id in self.applied_commands

    def mark_command_applied(self, cmd_id: str) -> None:
        if cmd_id not in self.applied_commands:
            self.applied_commands.append(cmd_id)
            if len(self.applied_commands) > 1000:
                self.applied_commands = self.applied_commands[-1000:]

    # -- follow spend cap --------------------------------------------------
    def follow_spent_today(self, day: str) -> float:
        return self.follow_spend.get(day, 0.0)

    def add_follow_spend(self, day: str, usd: float) -> None:
        self.follow_spend[day] = self.follow_spend.get(day, 0.0) + usd
