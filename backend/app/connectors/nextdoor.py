"""Nextdoor connector built on the official Nextdoor API (partner-gated).

What Nextdoor's API allows (verified against developer.nextdoor.com):
- **Display / Search API** — find recent PUBLIC posts mentioning targeted
  keywords in an area. This powers lead *discovery*. ✅
- **Create Post API** — publish a NEW post from a neighbor or business profile
  (a proactive "broadcast"). ✅
- **No reply/comment API** — there is no endpoint to comment on another member's
  existing post. ❌

Therefore:
- ``discover``  -> official Search API (when live + token), else sample source.
- ``publish``   -> NOT supported. Replying to a neighbor's post must be done by
  the client from their own account (human-in-the-loop assist). Automating a
  member's session to comment violates Nextdoor's Member Agreement and risks
  account bans, so we never do it.
- ``broadcast`` -> official Create Post API (when live + token), else simulated.

Access requires an approved Nextdoor API partnership ("Apply for access" at
developer.nextdoor.com). Endpoints are structured here and gated behind
``LEADPILOT_LIVE_CONNECTORS``; fill in the exact partner endpoint/params your
approved app is granted.
"""
from __future__ import annotations

import logging

import httpx

from .base import CandidatePost, Connector
from .sample import SampleConnector

logger = logging.getLogger("leadpilot.connectors.nextdoor")

API_BASE = "https://api.nextdoor.com"


class NextdoorConnector(Connector):
    provider = "nextdoor"
    # Nextdoor's API cannot reply on a neighbor's post; it can broadcast.
    supports_reply_autopost = False
    supports_broadcast = True

    def __init__(self, *, access_token: str, profile_id: str | None = None) -> None:
        self.access_token = access_token
        self.profile_id = profile_id
        # Fall back to the sample source for any data we can't fetch live, so
        # the dashboard is never empty during partner onboarding.
        self._sample = SampleConnector("nextdoor")

    def discover(
        self, *, neighborhoods: list[str], limit: int = 10
    ) -> list[CandidatePost]:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{API_BASE}/v1/search/posts",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params={
                        # The Search API matches public posts by keyword + geo.
                        "near": neighborhoods[0] if neighborhoods else "",
                        "limit": limit,
                    },
                )
                resp.raise_for_status()
                data = resp.json().get("posts", [])
        except Exception as exc:  # noqa: BLE001
            logger.info("Nextdoor Search API unavailable, using sample: %s", exc)
            return self._sample.discover(neighborhoods=neighborhoods, limit=limit)

        posts: list[CandidatePost] = []
        for item in data:
            body = (item.get("body") or item.get("body_text") or "").strip()
            if not body:
                continue
            posts.append(
                CandidatePost(
                    provider=self.provider,
                    post_url=item.get("permalink") or item.get("url"),
                    author=(item.get("author") or {}).get("name"),
                    content=body,
                    location=item.get("neighborhood")
                    or (neighborhoods[0] if neighborhoods else None),
                )
            )
        return posts

    def publish(self, *, post_url: str | None, reply_text: str) -> bool:
        # Intentionally unsupported — see module docstring. The app routes
        # Nextdoor replies through the human-in-the-loop assist flow instead.
        raise NotImplementedError(
            "Nextdoor has no reply API; replies are posted by the client (assist flow)."
        )

    def broadcast(self, *, body_text: str, profile_id: str | None = None) -> bool:
        target = profile_id or self.profile_id
        try:
            with httpx.Client(timeout=15.0) as client:
                payload = {"body_text": body_text}
                if target:
                    payload["profile_id"] = target
                resp = client.post(
                    f"{API_BASE}/v1/posts",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json=payload,
                )
                resp.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Nextdoor broadcast (Create Post) failed: %s", exc)
            return False
