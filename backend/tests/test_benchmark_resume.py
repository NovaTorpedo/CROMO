"""An interrupted AMD benchmark must keep what it measured, resume without redoing finished work, and publish a
partial run only with honest labels (no evaluation score, no full-audit cost). Runs against the mock vLLM server."""

import argparse
import asyncio
import dataclasses
import json
import sys
import tempfile
from pathlib import Path

import httpx
import pytest

from cromo import config, db, index, investigate, llm

from test_live_client import handler  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "eval"))

import benchmark_amd  # noqa: E402

STEPS = ["ALK-04", "SOL-02", "SOL-08"]


def _args(**kw):
    base = dict(skip_ingest=False, steps=list(STEPS), concurrency=1, rocm_smi=None, tag="", resume=False, finalize_partial=False)
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture
def live(monkeypatch):
    tmp = Path(tempfile.mkdtemp(prefix="cromo-bench-"))
    role = lambda name: config.RoleConfig(name, "http://mock-vllm.test/v1", "test-key", "mock-model")  # noqa: E731
    s = dataclasses.replace(config.settings, provider="amd", reasoner=role("reasoner"), vision=role("vision"),
                            embeddings=role("embeddings"), data_dir=tmp, metadata_source="auto", max_concurrency=4)
    monkeypatch.setattr(config, "settings", s)
    monkeypatch.setattr(llm, "_clients", {})
    monkeypatch.setattr(llm, "_client", lambda r: httpx.AsyncClient(base_url=r.base_url, transport=httpx.MockTransport(handler),
                                                                   headers={"Authorization": f"Bearer {r.api_key}"}))
    db.close()
    index.invalidate()
    yield s
    db.close()
    index.invalidate()


def test_interrupted_run_resumes_and_finalizes_honestly(live, monkeypatch):
    real = investigate.investigate
    seen: list[str] = []

    async def flaky(sid, emit=None):
        seen.append(sid)
        if sid == "SOL-08":
            raise RuntimeError("GPU server went away")
        return await real(sid, emit)

    monkeypatch.setattr(investigate, "investigate", flaky)
    with pytest.raises(RuntimeError):
        asyncio.run(benchmark_amd.run(_args()))
    partial = live.recorded_dir / "benchmark_amd.partial.json"
    saved = json.loads(partial.read_text(encoding="utf-8"))
    assert saved["ingest"]["scanned_pages"] > 0 and set(saved["durations"]) == {"ALK-04", "SOL-02"}
    assert not (live.recorded_dir / "benchmark_amd.json").exists()

    # publishing the partial run: labelled, no audit cost
    benchmark_amd.finalize_partial(_args())
    out = json.loads((live.recorded_dir / "benchmark_amd.json").read_text(encoding="utf-8"))
    assert out["complete"] is False and "PARTIAL" in out["note"]
    assert out["investigation"]["steps"] == 2 and out["cost"]["per_plant_audit_usd"] is None
    assert "eval" not in out

    # resuming: no new ingest, only the unfinished step is investigated
    seen.clear()
    monkeypatch.setattr(investigate, "investigate", real)
    asyncio.run(benchmark_amd.run(_args(resume=True)))
    out = json.loads((live.recorded_dir / "benchmark_amd.json").read_text(encoding="utf-8"))
    assert out["investigation"]["steps"] == 3 and out["ingest"] == saved["ingest"]
    assert "durations" not in out and not partial.exists()
    assert {p.stem for p in (live.recorded_dir / "runs").glob("*.json")} == set(STEPS)


def test_token_factory_claims_no_gpu_cost(live, monkeypatch):
    monkeypatch.setattr(config, "settings", dataclasses.replace(live, amd_route="tokenfactory"))
    c = benchmark_amd._cost(config.settings, 3600, True)
    assert c["per_plant_audit_usd"] is None and c["gpu_hours"] is None and "Token Factory" in c["basis"]
