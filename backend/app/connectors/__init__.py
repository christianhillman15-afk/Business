"""Pluggable social-platform connectors.

Each connector knows how to (a) discover candidate posts for a client and
(b) publish an approved reply. The sample connector ships an in-memory data
source so the product runs end-to-end without external credentials.

``connector_for`` is the factory the rest of the app uses. It returns a real
connector only when live connectors are explicitly enabled AND the account has
credentials — otherwise it returns the safe offline ``SampleConnector``. This is
the safety boundary described in docs/COMPLIANCE.md.
"""
from __future__ import annotations

from ..config import settings
from .base import CandidatePost, Connector
from .meta import MetaGraphConnector
from .sample import SampleConnector


def connector_for(provider: str, *, credential: str | None = None) -> Connector:
    if settings.leadpilot_live_connectors and credential:
        if provider == "facebook":
            return MetaGraphConnector(
                access_token=credential, group_ids=settings.meta_group_id_list
            )
        # Nextdoor has no public API; a real integration would go here behind
        # its own compliant path. Until then, fall through to the sample source.
    return SampleConnector(provider)


__all__ = ["CandidatePost", "Connector", "connector_for", "SampleConnector"]
