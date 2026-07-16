"""A compliant, offline sample connector.

It serves a fixed pool of realistic-looking community posts (a deliberate mix of
in-field and off-field requests) so the relevance matcher has something to chew
on. ``publish`` is a no-op that simply succeeds. No scraping, no automation of
anyone's real account.
"""
from __future__ import annotations

import random

from .base import CandidatePost, Connector

# A varied pool spanning several trades, so field-matching is actually tested.
_SAMPLE_POOL: list[dict] = [
    {
        "author": "Marcia P.",
        "content": "Does anyone know a good plumber? Our kitchen sink has been "
        "leaking under the cabinet for two days and it's getting worse.",
        "tags": ["plumbing"],
    },
    {
        "author": "Devon R.",
        "content": "Looking for a reliable house cleaner for a 3-bed home, "
        "every other week. Recommendations welcome!",
        "tags": ["cleaning"],
    },
    {
        "author": "The Okafor Family",
        "content": "Our backyard is a jungle after the rain. Need someone for "
        "lawn mowing and hedge trimming this weekend.",
        "tags": ["landscaping"],
    },
    {
        "author": "Sam T.",
        "content": "Water heater stopped producing hot water this morning. "
        "Any plumbers available for an emergency call?",
        "tags": ["plumbing"],
    },
    {
        "author": "Priya N.",
        "content": "Moving out next week and need a deep clean for the apartment "
        "to get my deposit back. Who do you all use?",
        "tags": ["cleaning"],
    },
    {
        "author": "Greg H.",
        "content": "Anyone do interior painting? Want to repaint two bedrooms "
        "before the holidays.",
        "tags": ["painting"],
    },
    {
        "author": "Lena M.",
        "content": "Recommendations for a handyman to mount a TV and fix a "
        "squeaky door?",
        "tags": ["handyman"],
    },
    {
        "author": "Carlos V.",
        "content": "Toilet keeps running and the shutoff valve is stuck. Need a "
        "plumber who can come out this week.",
        "tags": ["plumbing"],
    },
    {
        "author": "Aisha B.",
        "content": "Looking to get my gutters cleaned and some bushes trimmed "
        "before winter. Landscaper recommendations?",
        "tags": ["landscaping"],
    },
    {
        "author": "Community Board",
        "content": "Reminder: the neighborhood potluck is this Saturday at the "
        "park pavilion. Bring a dish to share!",
        "tags": ["noise"],
    },
]


class SampleConnector(Connector):
    # The offline connector simulates everything succeeding.
    supports_reply_autopost = True
    supports_broadcast = True

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def discover(
        self, *, neighborhoods: list[str], limit: int = 10
    ) -> list[CandidatePost]:
        location = neighborhoods[0] if neighborhoods else "Your Neighborhood"
        sample = random.sample(_SAMPLE_POOL, k=min(limit, len(_SAMPLE_POOL)))
        posts: list[CandidatePost] = []
        for i, item in enumerate(sample):
            posts.append(
                CandidatePost(
                    provider=self.provider,
                    post_url=f"https://example.test/{self.provider}/post/"
                    f"{random.randint(10_000, 99_999)}-{i}",
                    author=item["author"],
                    content=item["content"],
                    location=location,
                )
            )
        return posts

    def publish(self, *, post_url: str | None, reply_text: str) -> bool:
        # Real connectors post via the client's authorized account / official
        # API. The sample connector just reports success.
        return True

    def broadcast(self, *, body_text: str, profile_id: str | None = None) -> bool:
        return True
