"""System / AMD panel data: models, hardware, measured latencies, throughput, GPU memory, cost per audit,
evaluation results. Numbers come only from measurements (metrics table, benchmark files) - never invented."""

from __future__ import annotations

import json
import shutil
import subprocess
import time

import numpy as np

from . import config, db, evolus, llm


def _load(name: str):
    p = config.settings.recorded_dir / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def latency_stats(provider: str | None = None) -> list[dict]:
    rows = db.q("SELECT stage, role, model, provider, latency_ms, tokens_in, tokens_out, ok FROM metrics" +
                (" WHERE provider=?" if provider else ""), (provider,) if provider else ())
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r["stage"], r["role"], r["model"], r["provider"]), []).append(r)
    out = []
    for (stage, role, model, prov), rs in sorted(groups.items()):
        lat = np.array([r["latency_ms"] for r in rs if r["ok"]] or [0.0])
        out.append({"stage": stage, "role": role, "model": model, "provider": prov, "calls": len(rs),
                    "errors": sum(1 for r in rs if not r["ok"]), "p50_ms": round(float(np.percentile(lat, 50)), 1),
                    "p95_ms": round(float(np.percentile(lat, 95)), 1),
                    "tokens_in": int(sum(r["tokens_in"] or 0 for r in rs)),
                    "tokens_out": int(sum(r["tokens_out"] or 0 for r in rs))})
    return out


def gpu_snapshot() -> dict | None:
    exe = shutil.which("rocm-smi")
    if exe:
        try:
            out = subprocess.run([exe, "--showmeminfo", "vram", "--showuse", "--showproductname", "--json"],
                                 capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                return {"source": "rocm-smi (live)", "ts": time.time(), "data": json.loads(out.stdout)}
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    bench = _load("benchmark_amd.json")
    if bench and bench.get("gpu"):
        return {"source": "rocm-smi (recorded during benchmark)", **bench["gpu"]}
    return None


def summary() -> dict:
    s = config.settings
    return {
        "config": s.public_summary(),
        "mode": llm.mode(),
        "models_in_use": {r: llm.model_name(r) for r in ("reasoner", "vision", "embeddings")},
        "ingest": db.kv_get("ingest_stats"),
        "latency": latency_stats(),
        "benchmark": _load("benchmark_amd.json"),
        "eval": {"amd": _load("eval_amd.json"), "fixture": _load("eval_fixture.json")},
        "gpu": gpu_snapshot(),
        "evolus": evolus.usage() if s.evolus_configured else {"configured": False},
        "recordings": sorted(p.stem for p in (s.recorded_dir / "runs").glob("*.json")) if (s.recorded_dir / "runs").exists() else [],
    }
