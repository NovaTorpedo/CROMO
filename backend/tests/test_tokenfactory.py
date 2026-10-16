"""AMD Token Factory route: configuration defaults, shared pacing, retry handling, retrieval expansion, OCR metrics."""

import asyncio
import json
import sys
import time

import httpx

from conftest import ROOT
from cromo import config, index, llm


def _settings(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return config.load_settings()


def test_token_factory_route_defaults_every_role_to_the_team_key(monkeypatch):
    s = _settings(monkeypatch, CROMO_AMD_ROUTE="tokenfactory", AMD_TOKEN_FACTORY="rc-" + "0" * 48, CROMO_PROVIDER="amd",
                  CROMO_REASONER_MODEL="Gemma-4-31B-IT", CROMO_VISION_MODEL="Gemma-4-31B-IT", CROMO_EMBEDDINGS_MODEL="",
                  CROMO_RPM_LIMIT="", CROMO_MAX_CONCURRENCY="", CROMO_REQUEST_TIMEOUT_S="", CROMO_HARDWARE_LABEL="")
    assert s.is_live
    assert s.reasoner.base_url == config.TOKEN_FACTORY_BASE_URL and s.reasoner.api_key.startswith("rc-")
    assert s.vision.base_url == s.reasoner.base_url and s.vision.api_key == s.reasoner.api_key
    assert not s.embeddings.configured  # the Token Factory serves no embedding model
    assert (s.rpm_limit, s.max_concurrency, s.request_timeout_s) == (18, 6, 600)
    assert "Token Factory" in s.hardware_label
    assert "rc-" not in json.dumps(s.public_summary())  # the key never reaches the UI


def test_own_vllm_route_is_unchanged(monkeypatch):
    s = _settings(monkeypatch, CROMO_AMD_ROUTE="vllm", AMD_TOKEN_FACTORY="rc-" + "0" * 48, CROMO_REASONER_MODEL="m",
                  CROMO_REASONER_BASE_URL="", CROMO_RPM_LIMIT="", CROMO_REQUEST_TIMEOUT_S="")
    assert s.reasoner.base_url == "" and s.reasoner.api_key == ""  # the team key is only used on its own route
    assert s.rpm_limit == 0 and s.request_timeout_s == 120


def test_rate_limiter_paces_a_shared_window():
    async def go():
        lim = llm.RateLimiter(3, window_s=0.6)
        t0 = time.monotonic()
        for _ in range(5):
            await lim.acquire()
        return time.monotonic() - t0

    assert asyncio.run(go()) >= 0.55  # the 4th request had to wait for the first to leave the window


def test_rate_limiter_backoff_blocks_everyone():
    async def go():
        lim = llm.RateLimiter(100)
        lim.backoff(0.3)
        t0 = time.monotonic()
        await lim.acquire()
        return time.monotonic() - t0

    assert asyncio.run(go()) >= 0.25


def test_retry_after_is_honoured_and_backoff_grows():
    r = httpx.Response(429, headers={"retry-after": "7"})
    assert 7 <= llm._retry_after(r, 0) <= 8.6
    plain = httpx.Response(503)
    assert llm._retry_after(plain, 3) > llm._retry_after(plain, 0) - 1.5


def test_gateway_and_platform_error_shapes():
    assert llm._error_text(httpx.Response(400, json={"error": {"message": "model not supported"}})) == "model not supported"
    assert llm._error_text(httpx.Response(403, json={"detail": {"error": {"message": "account_not_verified"}}})) == "account_not_verified"


def test_live_call_retries_429_then_succeeds(monkeypatch):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "rate limited"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"ok\": true}"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 3, "completion_tokens": 2}})

    role = config.RoleConfig("reasoner", "http://tf.test/v1", "rc-x", "Gemma-4-31B-IT")
    monkeypatch.setattr(llm, "_retry_after", lambda r, a: 0.01)
    llm._clients[f"{role.role}:{role.base_url}"] = httpx.AsyncClient(base_url=role.base_url, transport=httpx.MockTransport(handler))
    try:
        text, meta = asyncio.run(llm._chat(role, [{"role": "user", "content": "hi"}], max_tokens=10, temperature=0,
                                           schema=None, stage="test.retry"))
    finally:
        llm._clients.pop(f"{role.role}:{role.base_url}", None)
    assert text == '{"ok": true}' and len(calls) == 2
    assert meta["latency_ms"] < 5000


def test_cut_off_answer_is_an_error_not_an_empty_result(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "", "reasoning": "..."}, "finish_reason": "length"}]})

    role = config.RoleConfig("reasoner", "http://tf2.test/v1", "", "m")
    llm._clients[f"{role.role}:{role.base_url}"] = httpx.AsyncClient(base_url=role.base_url, transport=httpx.MockTransport(handler))
    try:
        try:
            asyncio.run(llm._chat(role, [{"role": "user", "content": "hi"}], max_tokens=10, temperature=0, schema=None, stage="t"))
            raise AssertionError("expected ProviderError")
        except llm.ProviderError as e:
            assert "max_tokens" in str(e)
    finally:
        llm._clients.pop(f"{role.role}:{role.base_url}", None)


def test_document_expansion_only_for_model_metadata(monkeypatch):
    monkeypatch.delenv("CROMO_DOC_EXPANSION", raising=False)
    assert index.expansion_enabled("reasoner") and index.expansion_enabled("evolus-extractor")
    assert not index.expansion_enabled("fixture") and not index.expansion_enabled(None)
    monkeypatch.setenv("CROMO_DOC_EXPANSION", "off")
    assert not index.expansion_enabled("reasoner")
    terms = index._expansion_terms({"entities": {"keywords": ["gelling", "impolmonimento"]}, "summary": "Batch gelled."})
    assert terms["impolmonimento"] == 1 and terms["gell"] == 1  # stemmed; each term counted once


def test_ocr_metrics_are_fair_to_formatting_and_order():
    sys.path.insert(0, str(ROOT / "scripts"))
    from compare_models import score, word_f1

    ref = "[stamp] APPROVED Ref. CR-1995-009 Add ammonium chloride"
    md = "# Ref. CR-1995-009\n\n**Add ammonium chloride**\n\nAPPROVED"  # same words, Markdown, letterhead moved
    assert word_f1(md, ref) == 1.0
    assert score(md, ref) > 0.2  # strict CER counts reading order
    assert score("APPROVED Ref. CR-1995-009 Add ammonium chloride", ref) == 0.0  # markers are not penalised
    assert word_f1(None, ref) is None and score(None, ref) is None


def test_streamed_answer_is_assembled_with_usage(monkeypatch):
    sse = ('data: {"choices":[{"delta":{"content":"{\\"verdict\\": "}}]}\n\n'
           'data: {"choices":[{"delta":{"content":"\\"FENCE\\"}"},"finish_reason":"stop"}]}\n\n'
           'data: {"choices":[],"usage":{"prompt_tokens":11,"completion_tokens":5}}\n\n'
           'data: [DONE]\n\n')
    seen = []

    def handler(request: httpx.Request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse.encode())

    monkeypatch.setattr(config, "settings", config.load_settings())
    object.__setattr__(config.settings, "stream", True)  # frozen dataclass: set for this test only
    role = config.RoleConfig("reasoner", "http://tf3.test/v1", "rc-x", "Gemma-4-31B-IT")
    llm._clients[f"{role.role}:{role.base_url}"] = httpx.AsyncClient(base_url=role.base_url, transport=httpx.MockTransport(handler))
    try:
        text, meta = asyncio.run(llm._chat(role, [{"role": "user", "content": "hi"}], max_tokens=10, temperature=0,
                                           schema=None, stage="test.stream"))
    finally:
        llm._clients.pop(f"{role.role}:{role.base_url}", None)
        object.__setattr__(config.settings, "stream", False)
    assert seen[0]["stream"] is True
    assert text == '{"verdict": "FENCE"}'
    assert meta["completion_tokens"] == 5
