"""Pluggable social-platform connectors.

Each connector knows how to (a) discover candidate posts, (b) publish an
approved reply (where the platform's API allows it), and (c) broadcast a new
post from the client's own page. The sample connector ships an in-memory data
source so the product runs end-to-end without external credentials.

``connector_for`` returns a real connector only when live connectors are
explicitly enabled AND the account has credentials — otherwise the safe offline
``SampleConnector``. ``provider_capabilities`` is the static source of truth the
UI/API use to decide auto-post vs human-in-the-loop, independent of the live
flag. See docs/COMPLIANCE.md and docs/NEXTDOOR.md.
"""
from __future__ import annotations

from ..config import settings
from .base import CandidatePost, Connector
from .meta import MetaGraphConnector
from .nextdoor import NextdoorConnector
from .sample import SampleConnector

# Static per-platform capabilities, driven by what each platform's official API
# actually permits — NOT by which connector instance happens to run.
PROVIDER_CAPABILITIES: dict[str, dict[str, bool]] = {
    # Graph API can comment on posts and publish to a Page.
    "facebook": {"reply_autopost": True, "broadcast": True},
    # Nextdoor's API can publish new posts but cannot reply on neighbor posts.
    "nextdoor": {"reply_autopost": False, "broadcast": True},
}


def provider_capabilities(provider: str) -> dict[str, bool]:
    return PROVIDER_CAPABILITIES.get(
        provider, {"reply_autopost": True, "broadcast": False}
    )


def connector_for(provider: str, *, credential: str | None = None) -> Connector:
    if settings.leadpilot_live_connectors and credential:
        if provider == "facebook":
            return MetaGraphConnector(
                access_token=credential, group_ids=settings.meta_group_id_list
            )
        if provider == "nextdoor":
            return NextdoorConnector(access_token=credential)
    return SampleConnector(provider)


__all__ = [
    "CandidatePost",
    "Connector",
    "connector_for",
    "provider_capabilities",
    "PROVIDER_CAPABILITIES",
    "SampleConnector",
]
