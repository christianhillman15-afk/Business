"""Facebook connector backed by the official Meta Graph API.

This is the compliant integration path: it reads from Group/Page feeds the
connected account is authorized for and publishes comments through the Graph
API — no scraping, no browser-session automation.

Notes:
- Reading group feeds and publishing comments require the appropriate Meta app
  review + permissions (e.g. ``groups_access_member_info`` /
  ``publish_to_groups`` where still granted, or Page equivalents). Provision
  these on your Meta app before enabling live connectors.
- The connector is only selected when ``LEADPILOT_LIVE_CONNECTORS=true`` and the
  connected account has a stored access token (see ``connectors.connector_for``).
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings
from .base import CandidatePost, Connector

logger = logging.getLogger("leadpilot.connectors.meta")

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


class MetaGraphConnector(Connector):
    provider = "facebook"

    def __init__(self, *, access_token: str, group_ids: list[str]) -> None:
        self.access_token = access_token
        self.group_ids = group_ids

    def discover(
        self, *, neighborhoods: list[str], limit: int = 10
    ) -> list[CandidatePost]:
        posts: list[CandidatePost] = []
        if not self.group_ids:
            logger.info("No Meta group IDs configured; nothing to discover.")
            return posts

        with httpx.Client(timeout=15.0) as client:
            for gid in self.group_ids:
                try:
                    resp = client.get(
                        f"{GRAPH_BASE}/{gid}/feed",
                        params={
                            "fields": "id,message,from{name},permalink_url",
                            "limit": limit,
                            "access_token": self.access_token,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json().get("data", [])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Meta feed fetch failed for %s: %s", gid, exc)
                    continue

                for item in data:
                    message = (item.get("message") or "").strip()
                    if not message:
                        continue
                    posts.append(
                        CandidatePost(
                            provider=self.provider,
                            post_url=item.get("permalink_url")
                            or f"https://www.facebook.com/{item.get('id')}",
                            author=(item.get("from") or {}).get("name"),
                            content=message,
                            location=neighborhoods[0] if neighborhoods else None,
                        )
                    )
        return posts

    def publish(self, *, post_url: str | None, reply_text: str) -> bool:
        post_id = _post_id_from_url(post_url)
        if not post_id:
            logger.warning("Cannot publish: no Graph post id in %s", post_url)
            return False
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{GRAPH_BASE}/{post_id}/comments",
                    data={"message": reply_text, "access_token": self.access_token},
                )
                resp.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Meta publish failed: %s", exc)
            return False


def _post_id_from_url(post_url: str | None) -> str | None:
    """Extract a Graph post id (``<group>_<post>``) from a stored URL.

    Real Graph feed responses give us the id directly; we persist it inside the
    post URL when available. This helper handles both the id-bearing form and a
    plain permalink (which the caller should ideally store the id for instead).
    """
    if not post_url:
        return None
    # If we stored ".../<id>" where id looks like "123_456", use it.
    tail = post_url.rstrip("/").split("/")[-1]
    if "_" in tail and tail.replace("_", "").isdigit():
        return tail
    return None
