"""Unit tests for the security, crypto, and field-matching primitives."""
from __future__ import annotations

from app.ai.matcher import classify_lead
from app.crypto import decrypt, encrypt
from app.security import hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("s3cretpw")
    assert h != "s3cretpw"
    assert verify_password("s3cretpw", h)
    assert not verify_password("wrong", h)


def test_session_encryption_roundtrip():
    token = encrypt("fb-access-token-123")
    assert token is not None
    assert "fb-access-token-123" not in token  # not stored in clear
    assert decrypt(token) == "fb-access-token-123"


def test_field_match_in_trade():
    res = classify_lead(
        post_content="Our water heater is leaking, need a plumber today!",
        trade="plumbing",
        service_categories=["leak repair", "water heaters"],
    )
    assert res.is_relevant
    assert res.score >= 0.5


def test_field_match_out_of_trade():
    res = classify_lead(
        post_content="Looking for a reliable house cleaner every other week.",
        trade="plumbing",
        service_categories=["leak repair", "water heaters", "drain cleaning"],
    )
    assert not res.is_relevant
