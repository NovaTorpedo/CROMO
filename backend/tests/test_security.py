"""API security: traversal, validation, access token, headers, rate limits, CORS."""

import pytest
from fastapi.testclient import TestClient

from cromo import config


@pytest.fixture(scope="module")
def client(built):
    from cromo.api import app

    with TestClient(app) as c:
        yield c


def test_health_and_headers(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"


@pytest.mark.parametrize("path", [
    "/api/docs/..%2F..%2Fetc%2Fpasswd", "/api/docs/ACC-1/pages/1", "/api/docs/ACC-0001/pages/99",
    "/api/docs/ACC-0001%2F..%2F..%2F.env/pages/1", "/api/docs/..\\..\\.env",
])
def test_path_traversal_blocked(client, path):
    r = client.get(path)
    assert r.status_code in (400, 404, 422)
    assert "EVOLUS" not in r.text and "API_KEY" not in r.text


def test_invalid_step_ids(client):
    assert client.get("/api/steps/..%2F..%2Fetc").status_code in (400, 404)
    assert client.get("/api/steps/XYZ-01").status_code == 400
    assert client.get("/api/steps/ALK-99").status_code == 404


def test_input_validation(client):
    assert client.post("/api/v1/change-check", json={"proposal": "x"}).status_code == 422
    assert client.post("/api/v1/change-check", json={"proposal": "y" * 5000}).status_code == 422
    assert client.post("/api/tripwires/simulate", json={"type": "rm -rf", "from": "a b", "to": "c"}).status_code == 422


def test_change_check_blocks_a_fence(client):
    r = client.post("/api/v1/change-check", json={"proposal": "Remove step SOL-02 (bonding and earthing) to save time"})
    assert r.status_code == 200 and r.json()["decision"] == "blocked"


def test_access_token_required_when_set(client, monkeypatch):
    s = config.settings
    monkeypatch.setattr(config, "settings", s.__class__(**{**s.__dict__, "access_token": "test-passcode-123"}))
    assert client.post("/api/v1/change-check", json={"proposal": "Remove step SOL-02"}).status_code == 401
    ok = client.post("/api/v1/change-check", json={"proposal": "Remove step SOL-02"}, headers={"X-Access-Token": "test-passcode-123"})
    assert ok.status_code == 200
    assert client.get("/api/map").status_code == 200  # reads stay public
    assert client.post("/api/evolus/webhook?token=wrong", json={}).status_code == 401


def test_webhook_disabled_without_token(client):
    assert client.post("/api/evolus/webhook", json={}).status_code == 401


def test_no_secrets_in_public_config(client):
    body = client.get("/api/system").text
    for name in ("EVOLUS_API_KEY", "api_key", "X-ApiKey"):
        assert name not in body
    s = config.settings
    if s.evolus_api_key:
        assert s.evolus_api_key not in body


def test_rate_limit(client):
    codes = [client.post("/api/v1/change-check", json={"proposal": "Remove step EPX-05 please"}).status_code for _ in range(40)]
    assert 429 in codes


def test_no_open_cors(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") is None


def test_oversized_body_rejected(client):
    r = client.post("/api/v1/change-check", content=b"{" + b" " * 300_000 + b"}",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413
