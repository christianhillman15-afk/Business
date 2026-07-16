"""Subscription tier definitions.

Tiers are priced by the number of AI-assisted posts (links commented on) allowed
per day: $200/1, $250/2, $300/4, $350/6, $400/8.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_monthly: int  # USD
    daily_post_quota: int


PLANS: dict[str, Plan] = {
    "solo": Plan("solo", "Solo", 200, 1),
    "starter": Plan("starter", "Starter", 250, 2),
    "growth": Plan("growth", "Growth", 300, 4),
    "pro": Plan("pro", "Pro", 350, 6),
    "scale": Plan("scale", "Scale", 400, 8),
}

DEFAULT_PLAN_CODE = "growth"


def get_plan(code: str | None) -> Plan | None:
    if not code:
        return None
    return PLANS.get(code)
