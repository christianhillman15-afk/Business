"""Subscription tier definitions.

Tiers are priced by the number of AI-assisted posts allowed per day, matching
the product spec: $250/4, $300/6, $350/8, $400/10.
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
    "starter": Plan("starter", "Starter", 250, 4),
    "growth": Plan("growth", "Growth", 300, 6),
    "pro": Plan("pro", "Pro", 350, 8),
    "scale": Plan("scale", "Scale", 400, 10),
}

DEFAULT_PLAN_CODE = "growth"


def get_plan(code: str | None) -> Plan | None:
    if not code:
        return None
    return PLANS.get(code)
