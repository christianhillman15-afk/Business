"""Pytest configuration: isolated SQLite DB, offline AI, seeded data."""
from __future__ import annotations

import os
import tempfile

# Must be set BEFORE importing the app (engine binds at import time).
_TMP = tempfile.mkdtemp(prefix="leadpilot-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ENCRYPTION_KEY"] = "test-encryption-key"
os.environ["ANTHROPIC_API_KEY"] = ""  # force deterministic offline AI

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    seed()
    return TestClient(app)


def _token(client: TestClient, email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
def provider_headers(client: TestClient) -> dict:
    token = _token(client, "demo@leadpilot.io", "demo1234")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client: TestClient) -> dict:
    token = _token(client, "admin@leadpilot.io", "admin1234")
    return {"Authorization": f"Bearer {token}"}
