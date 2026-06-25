"""Pluggable social-platform connectors.

Each connector knows how to (a) discover candidate posts for a client and
(b) publish an approved reply. The sample connector ships an in-memory data
source so the product runs end-to-end without external credentials.

Real Facebook / Nextdoor connectors should be implemented against this same
interface. Read docs/COMPLIANCE.md before doing so.
"""
from .base import CandidatePost, Connector
from .sample import SampleConnector

# Registry keyed by provider value. Swap SampleConnector for a real connector
# (e.g. a Meta Graph API connector) without touching the rest of the app.
CONNECTORS: dict[str, Connector] = {
    "facebook": SampleConnector("facebook"),
    "nextdoor": SampleConnector("nextdoor"),
}

__all__ = ["CandidatePost", "Connector", "CONNECTORS"]
