"""Exercise the LIVE code path (prompts -> OpenAI-compatible HTTP -> JSON parsing -> validation) against a
mock vLLM server, so the first real AMD run does not discover plumbing bugs. The mock 'model' parses the
rendered prompts and answers with the fixture heuristics, which proves the prompts carry everything needed."""

import asyncio
import base64
import dataclasses
import json
import re
import tempfile
from pathlib import Path

import httpx

from cromo import config, db, fixture, index, ingest, investigate, llm

DOC_RE = re.compile(r'<document id="([^"]+)" accession="([^"]+)" date="([^"]+)" type="([^"]*)" title="([^"]*)">\n(.*?)\n</document>', re.S)
EV_RE = re.compile(r'^(E\d+) \[([^,]+), ([^,]+), ([^,]+), stance=(\w+)\]: (.*?) \| quote: "(.*)"$', re.M)
calls: list[str] = []


def _passages(user: str):
    return [{"id": m[0], "acc": m[1], "date": None if m[2] == "unknown" else m[2], "doc_type": m[3], "title": m[4], "text": m[5]}
            for m in DOC_RE.findall(user)]


def fake_model(system: str, user: str) -> dict:
    if "extract structured metadata" in system:
        calls.append("meta")
        acc, text = re.search(r'<document id="D" accession="([^"]+)">\n(.*)\n</document>', user, re.S).groups()
        return fixture.metadata(acc, text)
    if "extract evidence about the step" in system:
        calls.append("read")
        sid, text = re.search(r"STEP UNDER INVESTIGATION: (\S+) - (.*)", user).groups()
        purpose = re.search(r"Current focus: (\w+)", user).group(1)
        return fixture.read({"step_id": sid, "step_text": text, "purpose": purpose, "passages": _passages(user)})
    if "Decide the status" in system:
        calls.append("conclude")
        sid, text = re.search(r"STEP: (\S+) - (.*)", user).groups()
        ev = [{"id": m[0], "acc": m[1], "date": None if m[2] == "undated" else m[2], "doc_type": m[3], "stance": m[4],
               "claim": m[5], "quote": m[6], "entities": fixture.entities_in(m[6])} for m in EV_RE.findall(user)]
        return fixture.conclude({"step_id": sid, "step_text": text, "evidence": ev})
    raise AssertionError("unexpected task prompt: " + system[:80])


def handler(request: httpx.Request) -> httpx.Response:
    assert request.headers.get("authorization") == "Bearer test-key"
    path = request.url.path
    if path.endswith("/models"):
        return httpx.Response(200, json={"data": [{"id": "mock-model"}]})
    body = json.loads(request.content)
    if path.endswith("/embeddings"):
        vecs = fixture.embed(body["input"])
        return httpx.Response(200, json={"data": [{"index": i, "embedding": v.tolist()} for i, v in enumerate(vecs)],
                                         "usage": {"prompt_tokens": 10}})
    msgs = body["messages"]
    content = msgs[-1]["content"]
    if isinstance(content, list):  # vision request
        url = next(c["image_url"]["url"] for c in content if c["type"] == "image_url")
        data = base64.b64decode(url.split(",", 1)[1])
        lines = fixture.transcribe(data)["lines"]
        text = "\n".join(ln["text"] for ln in lines)
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 900, "completion_tokens": 200}})
    out = fake_model(msgs[0]["content"], content)
    # wrap in a code fence and a thinking block, like real models sometimes do
    text = "<think>checking</think>\n```json\n" + json.dumps(out) + "\n```"
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 1500, "completion_tokens": 300}})


def test_full_pipeline_through_openai_compatible_endpoints(monkeypatch):
    tmp = Path(tempfile.mkdtemp(prefix="cromo-live-"))
    role = lambda name: config.RoleConfig(name, "http://mock-vllm.test/v1", "test-key", "mock-model")  # noqa: E731
    live = dataclasses.replace(config.settings, provider="amd", reasoner=role("reasoner"), vision=role("vision"),
                               embeddings=role("embeddings"), data_dir=tmp, metadata_source="auto", max_concurrency=4)
    monkeypatch.setattr(config, "settings", live)
    monkeypatch.setattr(llm, "_clients", {})
    monkeypatch.setattr(llm, "_client", lambda r: httpx.AsyncClient(base_url=r.base_url, transport=httpx.MockTransport(handler),
                                                                   headers={"Authorization": f"Bearer {r.api_key}"}))
    db.close()
    index.invalidate()
    try:
        async def go():
            st = await ingest.ingest_all(force=True)
            assert st["provider"] == "amd" and st["scanned_pages"] > 0
            v = await investigate.investigate("ALK-04")
            await llm.aclose()
            return v

        v = asyncio.run(go())
        assert v["provider"] == "amd" and v["model"] == "mock-model"
        assert v["verdict"] in ("FOSSIL", "FENCE", "ACTIVE", "UNKNOWN") and v["hops"] >= 3
        assert {"meta", "read", "conclude"} <= set(calls)
        src = {r["source"] for r in db.q("SELECT DISTINCT source FROM pages")}
        assert "vision" in src and "text_layer" in src
        assert db.q1("SELECT COUNT(*) n FROM metrics WHERE provider='amd'")["n"] > 0
    finally:
        db.close()
        index.invalidate()
