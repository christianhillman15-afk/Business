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

    Capabilities differ by platform and drive the product's workflow:

    - ``supports_reply_autopost`` — can the platform's official API post a reply
      on *another member's* existing post? Facebook's Graph API can; Nextdoor's
      API cannot (only new posts), so Nextdoor replies are human-in-the-loop.
    - ``supports_broadcast`` — can the API publish a *new* post from the client's
      own page/profile (a proactive "broadcast")? Both Facebook and Nextdoor can.

    Implementations must respect platform Terms of Service and the client's own
    connected, authorized account.
    """

    provider: str
    supports_reply_autopost: bool = False
    supports_broadcast: bool = False

    @abstractmethod
    def discover(
        self, *, neighborhoods: list[str], limit: int = 10
    ) -> list[CandidatePost]:
        ...

    @abstractmethod
    def publish(self, *, post_url: str | None, reply_text: str) -> bool:
        """Post an approved reply on an existing post. Only meaningful when
        ``supports_reply_autopost`` is True."""
        ...

    def broadcast(self, *, body_text: str, profile_id: str | None = None) -> bool:
        """Publish a new post from the client's own page/profile."""
        raise NotImplementedError(
            f"{self.provider} connector does not support broadcast posts"
        )
