"""Connector interface shared by all social-platform integrations."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CandidatePost:
    provider: str
    post_url: str | None
    author: str | None
    content: str
    location: str | None

    def dedup_key(self, user_id: int) -> str:
        basis = f"{user_id}:{self.provider}:{self.post_url or self.content[:120]}"
        return hashlib.sha256(basis.encode()).hexdigest()[:32]


class Connector(ABC):
    """A social-platform integration.

    ``discover`` returns candidate posts near the client; ``publish`` posts an
    approved reply. Implementations must respect platform Terms of Service and
    the client's own connected, authorized account.
    """

    provider: str

    @abstractmethod
    def discover(
        self, *, neighborhoods: list[str], limit: int = 10
    ) -> list[CandidatePost]:
        ...

    @abstractmethod
    def publish(self, *, post_url: str | None, reply_text: str) -> bool:
        ...
