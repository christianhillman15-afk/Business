"""Integration tests for the LeadPilot API (offline AI, seeded DB)."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_register_and_login(client: TestClient):
    email = f"new-{uuid.uuid4().hex[:8]}@leadpilot.io"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "plan_code": "starter"},
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_profile_update(client: TestClient, provider_headers: dict):
    res = client.put(
        "/api/profile",
        headers=provider_headers,
        json={
            "trade": "plumbing",
            "service_categories": ["leak repair", "drain cleaning"],
            "price_list": "Service call $89",
            "phone": "(555) 000-1111",
            "target_neighborhoods": ["Rivertown"],
        },
    )
    assert res.status_code == 200
    assert res.json()["trade"] == "plumbing"
    assert "leak repair" in res.json()["service_categories"]


def _collect_draft(client: TestClient, headers: dict) -> dict | None:
    """Run discovery (retrying for randomness) until a drafted lead appears."""
    for _ in range(5):
        leads = client.post("/api/leads/discover", headers=headers).json()
        for lead in leads:
            if lead["status"] == "drafted" and lead["response"]:
                return lead
    return None


def test_discovery_and_field_matching(client: TestClient, provider_headers: dict):
    leads = client.post("/api/leads/discover", headers=provider_headers).json()
    assert isinstance(leads, list)
    # Every lead is classified with a relevance score.
    for lead in leads:
        assert lead["relevance_score"] is not None
        assert lead["status"] in {
            "matched",
            "irrelevant",
            "drafted",
            "engaged",
            "dismissed",
        }
    # Drafted leads carry an AI reply ready for review.
    for lead in leads:
        if lead["status"] == "drafted":
            assert lead["response"]["status"] == "draft"
            assert lead["response"]["generated_text"]


def test_approve_decrements_quota(client: TestClient, provider_headers: dict):
    before = client.get("/api/leads/quota", headers=provider_headers).json()
    draft = _collect_draft(client, provider_headers)
    assert draft is not None, "expected at least one drafted lead"
    rid = draft["response"]["id"]
    res = client.post(f"/api/responses/{rid}/approve", headers=provider_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "posted"
    after = client.get("/api/leads/quota", headers=provider_headers).json()
    assert after["used_today"] == before["used_today"] + 1


def test_support_chat_and_escalation(client: TestClient, provider_headers: dict):
    res = client.post(
        "/api/support/chat",
        headers=provider_headers,
        json={"message": "How do I connect my Nextdoor account?"},
    )
    assert res.status_code == 200
    assert res.json()["reply"]
    assert res.json()["escalated"] is False

    esc = client.post(
        "/api/support/chat",
        headers=provider_headers,
        json={"message": "I want a refund, this charged me twice"},
    )
    assert esc.json()["escalated"] is True


def test_admin_requires_admin(client: TestClient, provider_headers: dict):
    res = client.get("/api/admin/stats", headers=provider_headers)
    assert res.status_code == 403


def test_admin_stats_and_recruiting(client: TestClient, admin_headers: dict):
    stats = client.get("/api/admin/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert "providers" in stats.json()

    recruits = client.post("/api/admin/recruiting/run", headers=admin_headers).json()
    assert isinstance(recruits, list)
    listing = client.get("/api/admin/recruits", headers=admin_headers).json()
    assert len(listing) >= len(recruits)


def test_capabilities(client: TestClient, provider_headers: dict):
    caps = client.get("/api/capabilities", headers=provider_headers).json()
    # Facebook can auto-reply; Nextdoor cannot (no reply API).
    assert caps["facebook"]["reply_autopost"] is True
    assert caps["nextdoor"]["reply_autopost"] is False
    assert caps["nextdoor"]["broadcast"] is True


def _collect_draft_for(client: TestClient, headers: dict, provider: str) -> dict | None:
    for _ in range(8):
        leads = client.post("/api/leads/discover", headers=headers).json()
        for lead in leads:
            if (
                lead["provider"] == provider
                and lead["status"] == "drafted"
                and lead["response"]
            ):
                return lead
    return None


def test_nextdoor_reply_is_human_in_the_loop(
    client: TestClient, provider_headers: dict
):
    lead = _collect_draft_for(client, provider_headers, "nextdoor")
    assert lead is not None, "expected a drafted Nextdoor lead"
    rid = lead["response"]["id"]
    # Auto-posting is blocked for Nextdoor (no reply API).
    blocked = client.post(f"/api/responses/{rid}/approve", headers=provider_headers)
    assert blocked.status_code == 409
    # The client posts it themselves, then confirms via mark-posted.
    done = client.post(f"/api/responses/{rid}/mark-posted", headers=provider_headers)
    assert done.status_code == 200
    assert done.json()["status"] == "posted"


def test_broadcast_business_post(client: TestClient, provider_headers: dict):
    draft = client.post(
        "/api/broadcast/draft",
        headers=provider_headers,
        json={"provider": "nextdoor", "topic": "drain cleaning special"},
    )
    assert draft.status_code == 201
    post = draft.json()
    assert post["status"] == "draft"
    assert post["body_text"]
    pub = client.post(
        f"/api/broadcast/{post['id']}/publish", headers=provider_headers
    )
    assert pub.status_code == 200
    assert pub.json()["status"] == "posted"


def test_billing_select_mock(client: TestClient, provider_headers: dict):
    res = client.post(
        "/api/subscription/select",
        headers=provider_headers,
        json={"plan_code": "pro"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["subscription"]["plan_code"] == "pro"
    assert body["subscription"]["status"] == "active"
    assert body["checkout_url"] is None  # mock provider
