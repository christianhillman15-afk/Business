"""Integration tests for the LeadPilot API (offline AI, seeded DB)."""
from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient


def _fresh_provider(client: TestClient) -> dict:
    email = f"u-{uuid.uuid4().hex[:8]}@leadpilot.io"
    tok = client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


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


def test_connect_methods_need_no_password(client: TestClient):
    # A fresh provider connects without ever sending a password/credential.
    email = f"conn-{uuid.uuid4().hex[:8]}@leadpilot.io"
    tok = client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    # OAuth: no credential in the request body.
    oa = client.post("/api/accounts", headers=h, json={"provider": "facebook", "auth_method": "oauth"})
    assert oa.status_code == 201
    assert oa.json()["auth_method"] == "oauth"
    assert oa.json()["health"] == "healthy"

    # Managed Business Page: no credential, starts provisioning.
    mg = client.post(
        "/api/accounts",
        headers=h,
        json={"provider": "nextdoor", "auth_method": "managed_business_page"},
    )
    assert mg.status_code == 201
    assert mg.json()["auth_method"] == "managed_business_page"
    assert mg.json()["health"] == "provisioning"


def test_admin_provisioning_and_activate(client: TestClient, admin_headers: dict):
    # Create a provider with a managed page awaiting setup.
    email = f"prov-{uuid.uuid4().hex[:8]}@leadpilot.io"
    tok = client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    client.post(
        "/api/accounts",
        headers={"Authorization": f"Bearer {tok}"},
        json={"provider": "nextdoor", "auth_method": "managed_business_page"},
    )
    queue = client.get("/api/admin/provisioning", headers=admin_headers).json()
    mine = [q for q in queue if q["email"] == email]
    assert mine, "managed page should appear in the provisioning queue"
    act = client.post(
        f"/api/admin/accounts/{mine[0]['id']}/activate", headers=admin_headers
    )
    assert act.status_code == 200
    assert act.json()["health"] == "healthy"


def test_passwordless_trial_and_magic_login(client: TestClient, admin_headers: dict):
    from app.security import create_magic_token

    email = f"trial-{uuid.uuid4().hex[:8]}@leadpilot.io"
    r = client.post(
        "/api/auth/start-trial",
        json={
            "email": email,
            "business_name": "Pipes R Us",
            "phone": "(555) 100-2000",
            "nextdoor_handle": "pipesrus",
        },
    )
    assert r.status_code == 201
    assert r.json()["created"] is True
    # Idempotent: same email doesn't duplicate.
    again = client.post("/api/auth/start-trial", json={"email": email})
    assert again.json()["created"] is False

    # Magic-link request always 200 (no account enumeration).
    assert client.post("/api/auth/magic/request", json={"email": email}).status_code == 200

    # Find the user id (admin) and verify a magic token logs in with no password.
    users = client.get("/api/admin/users", headers=admin_headers).json()
    uid = next(u["id"] for u in users if u["email"] == email)
    bad = client.post("/api/auth/magic/verify", json={"token": "nope"})
    assert bad.status_code == 400
    good = client.post(
        "/api/auth/magic/verify", json={"token": create_magic_token(uid)}
    )
    assert good.status_code == 200
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {good.json()['access_token']}"},
    ).json()
    assert me["email"] == email
    assert me["nextdoor_handle"] == "pipesrus"
    assert me["onboarding_source"] == "trial_page"


def test_convert_recruit_to_trial(client: TestClient, admin_headers: dict):
    recruits = client.post("/api/admin/recruiting/run", headers=admin_headers).json()
    if not recruits:
        recruits = client.get("/api/admin/recruits", headers=admin_headers).json()
    rid = recruits[0]["id"]
    email = f"recruit-{uuid.uuid4().hex[:8]}@leadpilot.io"
    res = client.post(
        f"/api/admin/recruits/{rid}/convert",
        headers=admin_headers,
        json={"email": email, "phone": "(555) 222-3333"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["converted_user_id"] is not None
    assert body["email"] == email
    assert body["trial_signup_at"] is not None


def test_trial_quota_is_one_per_day(client: TestClient):
    h = _fresh_provider(client)  # new accounts start on a trial
    q = client.get("/api/leads/quota", headers=h).json()
    assert q["on_trial"] is True
    assert q["daily_quota"] == 1


def test_sms_console_send():
    from app.sms import send_sms

    assert send_sms("+15551234567", "hello") is True
    assert send_sms(None, "no recipient") is False


def test_leads_texted_on_discovery(client: TestClient, monkeypatch):
    import app.services as services

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(services, "send_sms", lambda to, body: sent.append((to, body)) or True)

    h = _fresh_provider(client)
    # Give them a phone (SMS is on by default).
    client.patch("/api/account", headers=h, json={"phone": "(555) 100-2000"})
    leads = client.post("/api/leads/discover", headers=h).json()
    drafted = [l for l in leads if l["status"] == "drafted"]

    # Two texts per drafted lead: the lead, then the reply on its own.
    assert len(sent) == 2 * len(drafted)
    if drafted:
        # Every other message is a bare reply (easy to copy) with no header.
        assert any("🔔 New" in body for _, body in sent)


def test_toggle_sms_off(client: TestClient, provider_headers: dict):
    me = client.patch(
        "/api/account", headers=provider_headers, json={"sms_enabled": False}
    ).json()
    assert me["sms_enabled"] is False


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


def test_notifications_lifecycle(client: TestClient):
    h = _fresh_provider(client)
    # Registration creates a welcome notification.
    notes = client.get("/api/notifications", headers=h).json()
    assert any(n["kind"] == "welcome" for n in notes)
    assert client.get("/api/notifications/unread-count", headers=h).json()["unread"] >= 1
    nid = notes[0]["id"]
    assert client.post(f"/api/notifications/{nid}/read", headers=h).json()["read"] is True
    client.post("/api/notifications/read-all", headers=h)
    assert client.get("/api/notifications/unread-count", headers=h).json()["unread"] == 0


def test_oauth_simulated_connect(client: TestClient):
    h = _fresh_provider(client)
    start = client.get("/api/accounts/oauth/facebook/start", headers=h).json()
    assert start["simulated"] is True
    qs = parse_qs(urlparse(start["authorize_url"]).query)
    cb = client.get(
        "/api/accounts/oauth/facebook/callback",
        params={"code": "dev-simulated", "state": qs["state"][0], "simulated": 1},
        follow_redirects=False,
    )
    assert cb.status_code == 303
    accts = client.get("/api/accounts", headers=h).json()
    assert any(
        a["provider"] == "facebook" and a["auth_method"] == "oauth" for a in accts
    )


def test_broadcast_schedule(client: TestClient):
    h = _fresh_provider(client)
    post = client.post(
        "/api/broadcast/draft", headers=h, json={"provider": "nextdoor"}
    ).json()
    sched = client.post(
        f"/api/broadcast/{post['id']}/schedule",
        headers=h,
        json={"scheduled_for": "2030-01-01T12:00:00"},
    )
    assert sched.status_code == 200
    assert sched.json()["status"] == "scheduled"
    assert sched.json()["scheduled_for"] is not None


def test_broadcast_frequency_guard(client: TestClient):
    h = _fresh_provider(client)
    first = client.post(
        "/api/broadcast/draft", headers=h, json={"provider": "nextdoor"}
    ).json()
    assert client.post(f"/api/broadcast/{first['id']}/publish", headers=h).status_code == 200
    # A second Business Post immediately after is blocked by the frequency guard.
    second = client.post(
        "/api/broadcast/draft", headers=h, json={"provider": "nextdoor"}
    ).json()
    blocked = client.post(f"/api/broadcast/{second['id']}/publish", headers=h)
    assert blocked.status_code == 429


def test_account_update(client: TestClient, provider_headers: dict):
    r = client.patch(
        "/api/account",
        headers=provider_headers,
        json={"business_name": "Renamed Co", "phone": "(555) 999-0000", "timezone": "America/Chicago"},
    )
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=provider_headers).json()
    assert me["business_name"] == "Renamed Co"
    assert me["timezone"] == "America/Chicago"


def test_set_password_on_passwordless_account(client: TestClient, admin_headers: dict):
    from app.security import create_magic_token

    email = f"pw-{uuid.uuid4().hex[:8]}@leadpilot.io"
    client.post("/api/auth/start-trial", json={"email": email})
    uid = next(
        u["id"]
        for u in client.get("/api/admin/users", headers=admin_headers).json()
        if u["email"] == email
    )
    h = {
        "Authorization": f"Bearer "
        + client.post(
            "/api/auth/magic/verify", json={"token": create_magic_token(uid)}
        ).json()["access_token"]
    }
    # Passwordless account can set a password without a current one.
    sp = client.post("/api/account/password", headers=h, json={"new_password": "brandnew123"})
    assert sp.status_code == 200
    # And can now log in with it.
    assert client.post(
        "/api/auth/login", json={"email": email, "password": "brandnew123"}
    ).status_code == 200


def test_expired_trial_blocks_actions(client: TestClient):
    from datetime import datetime

    from app.database import SessionLocal
    from app.models import SubscriptionStatus, User

    h = _fresh_provider(client)
    me = client.get("/api/auth/me", headers=h).json()

    db = SessionLocal()
    try:
        u = db.get(User, me["id"])
        u.subscription.status = SubscriptionStatus.trialing
        u.subscription.trial_end = datetime(2000, 1, 1)  # already expired
        db.commit()
    finally:
        db.close()

    # Value-delivering actions are now blocked with 402 until they pick a plan.
    assert client.post("/api/leads/discover", headers=h).status_code == 402

    # Subscribing restores access.
    client.post("/api/subscription/select", headers=h, json={"plan_code": "growth"})
    assert client.post("/api/leads/discover", headers=h).status_code == 200


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


def test_support_suggestions(client: TestClient, provider_headers: dict):
    res = client.get("/api/support/suggestions", headers=provider_headers)
    assert res.status_code == 200
    suggestions = res.json()["suggestions"]
    assert isinstance(suggestions, list) and len(suggestions) >= 3


def test_sms_inbound_known_number_answers(client: TestClient):
    h = _fresh_provider(client)
    client.patch("/api/account", headers=h, json={"phone": "(555) 770-1234"})
    res = client.post(
        "/api/sms/inbound",
        data={"From": "+15557701234", "Body": "what does it cost?"},
    )
    assert res.status_code == 200
    assert "<Message>" in res.text
    assert "$" in res.text  # pricing answer includes a dollar figure


def test_sms_inbound_unknown_number_prompts_linking(client: TestClient):
    res = client.post(
        "/api/sms/inbound",
        data={"From": "+19998887777", "Body": "hello"},
    )
    assert res.status_code == 200
    assert "isn't linked" in res.text


def test_sms_inbound_two_way_remembers_conversation(client: TestClient):
    h = _fresh_provider(client)
    client.patch("/api/account", headers=h, json={"phone": "(555) 770-9999"})
    # Two texts from the same number should reuse the running conversation.
    client.post(
        "/api/sms/inbound",
        data={"From": "+15557709999", "Body": "how do I get leads by text?"},
    )
    second = client.post(
        "/api/sms/inbound",
        data={"From": "+15557709999", "Body": "and how much does it cost?"},
    )
    assert second.status_code == 200
    assert "<Message>" in second.text


def test_notifications_texted_to_customer(client: TestClient, monkeypatch):
    import app.notifications as notifications

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        notifications, "send_sms", lambda to, body: sent.append((to, body)) or True
    )
    h = _fresh_provider(client)
    client.patch("/api/account", headers=h, json={"phone": "(555) 330-7788"})
    lead = _collect_draft_for(client, h, "facebook")
    assert lead is not None, "expected a drafted Facebook lead"
    rid = lead["response"]["id"]
    res = client.post(f"/api/responses/{rid}/approve", headers=h)
    assert res.status_code == 200
    # The "reply posted" notification was delivered as a text.
    assert len(sent) >= 1 and all(body for _, body in sent)


def test_sms_command_status_and_help(client: TestClient):
    h = _fresh_provider(client)
    client.patch("/api/account", headers=h, json={"phone": "(555) 880-1212"})
    status = client.post(
        "/api/sms/inbound", data={"From": "+15558801212", "Body": "STATUS"}
    )
    assert status.status_code == 200 and "Plan:" in status.text
    helped = client.post(
        "/api/sms/inbound", data={"From": "+15558801212", "Body": "HELP"}
    )
    assert "STATUS" in helped.text and "STOP" in helped.text


def test_sms_command_stop_and_start_opt_out(client: TestClient):
    h = _fresh_provider(client)
    client.patch("/api/account", headers=h, json={"phone": "(555) 881-3434"})
    stop = client.post(
        "/api/sms/inbound", data={"From": "+15558813434", "Body": "stop"}
    )
    assert "unsubscribed" in stop.text
    assert client.get("/api/auth/me", headers=h).json()["sms_enabled"] is False
    client.post("/api/sms/inbound", data={"From": "+15558813434", "Body": "START"})
    assert client.get("/api/auth/me", headers=h).json()["sms_enabled"] is True
