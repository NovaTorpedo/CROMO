"""API security: traversal, validation, access token, headers, rate limits, CORS."""

import pytest
from fastapi.testclient import TestClient

from cromo import config


@pytest.fixture(scope="module")
def client(built):
    from cromo.api import app

    with TestClient(app, client=("127.0.0.1", 50000)) as c:
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


def test_replay_streams_recorded_run_with_label(client):
    import json as _json

    from cromo import config as _c, investigate

    runs = _c.settings.recorded_dir / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    f = runs / "ALK-04.json"
    f.write_text(_json.dumps({"step_id": "ALK-04", "recorded_at": 1.0, "provider": "test-recording", "models": {"reasoner": "x"},
                              "hardware": "test", "events": investigate.stored_events("ALK-04")}), encoding="utf-8")
    try:
        r = client.get("/api/steps/ALK-04/replay?speed=8")
        lines = [_json.loads(x) for x in r.text.splitlines() if x.strip()]
        assert lines[0]["type"] == "replay" and lines[0]["provider"] == "test-recording"
        assert lines[-1]["type"] == "verdict"
        assert client.get("/api/steps/EPX-01/replay").status_code == 404
    finally:
        f.unlink()


def test_unmappable_change_is_never_allowed(client):
    from cromo import security as _s

    _s._hits.clear()
    r = client.post("/api/v1/change-check", json={"proposal": "Please make the plant more efficient somehow"})
    assert r.status_code == 200 and r.json()["decision"] == "caution"


@pytest.fixture
def remote(built):
    """A caller on the internet (public IP), as on a public deployment."""
    from cromo import security as _s
    from cromo.api import app

    _s._hits.clear()
    with TestClient(app, client=("203.0.113.9", 40000)) as c:
        yield c


def test_writes_fail_closed_for_remote_callers_without_token(remote, monkeypatch):
    s = config.settings
    monkeypatch.setattr(config, "settings", s.__class__(**{**s.__dict__, "access_token": ""}))
    for path, body in (("/api/v1/change-check", {"proposal": "Remove step SOL-02"}), ("/api/ask", {"question": "why?"}),
                       ("/api/tripwires/simulate", {"type": "supplier_switch", "from": "a", "to": "b"}),
                       ("/api/steps/ALK-04/investigate", None), ("/api/trials", {"step_id": "ALK-04"})):
        assert remote.post(path, json=body).status_code == 403, path
    assert remote.post("/api/trials/TR-000000/refresh").status_code == 403
    assert remote.get("/api/map").status_code == 200  # reads stay public


def test_proxied_local_caller_is_not_trusted(client, monkeypatch):
    from cromo import security as _s

    _s._hits.clear()
    s = config.settings
    monkeypatch.setattr(config, "settings", s.__class__(**{**s.__dict__, "access_token": ""}))
    r = client.post("/api/v1/change-check", json={"proposal": "Remove step SOL-02"}, headers={"X-Forwarded-For": "198.51.100.4"})
    assert r.status_code == 403


def test_remote_caller_with_token(remote, monkeypatch):
    s = config.settings
    monkeypatch.setattr(config, "settings", s.__class__(**{**s.__dict__, "access_token": "test-passcode-456"}))
    assert remote.post("/api/v1/change-check", json={"proposal": "Remove step SOL-02"}).status_code == 401
    ok = remote.post("/api/v1/change-check", json={"proposal": "Remove step SOL-02"}, headers={"X-Access-Token": "test-passcode-456"})
    assert ok.status_code == 200


def test_api_docs_hidden_by_default(client):
    assert client.get("/api/openapi.json").status_code == 404
    assert client.get("/api/docs-ui").status_code == 404


def test_global_rate_limit_on_reads(remote, monkeypatch):
    from cromo import security as _s

    monkeypatch.setattr(_s, "GLOBAL_LIMIT_PER_MIN", 5)
    codes = [remote.get("/api/health").status_code for _ in range(8)]
    assert codes[:5] == [200] * 5 and 429 in codes
    _s._hits.clear()


def test_internal_errors_are_generic(monkeypatch):
    from cromo import api as _api

    def boom():
        raise RuntimeError("secret detail C:/internal/path model=xyz")

    monkeypatch.setattr(_api.tripwires, "registry", boom)
    from cromo import security as _s

    _s._hits.clear()
    with TestClient(_api.app, client=("127.0.0.1", 50001), raise_server_exceptions=False) as c:
        r = c.get("/api/tripwires")
    assert r.status_code == 500 and r.json() == {"detail": "Internal server error."}


def test_upstream_errors_are_not_shown(caplog):
    from cromo import evolus, llm

    e = llm.ProviderError("reasoner endpoint HTTP 500", detail="upstream body with internals")
    assert "upstream" not in str(e)
    e2 = evolus.EvolusError("Evolus request failed (HTTP 400)", 400, detail="POST /workflows/abc/execute: body")
    assert "workflows" not in str(e2)


def test_access_log_redacts_query_tokens():
    import logging

    from cromo.security import RedactQueryTokens

    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("192.0.2.1:5", "POST", "/api/evolus/webhook?token=s3cr3t-value&x=1", "1.1", 200), None)
    RedactQueryTokens().filter(rec)
    assert "s3cr3t-value" not in rec.getMessage() and "token=[redacted]" in rec.getMessage()
