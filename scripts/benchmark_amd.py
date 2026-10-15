"""Benchmark CROMO on AMD and record real runs for demo replay.

Measures (on the configured AMD endpoints, nothing estimated):
  * ingestion throughput: pages/min overall and scanned pages/min read by the VLM
  * transcription accuracy of the VLM on the scanned/handwritten pages (character error rate vs. the
    recorded reference transcriptions)
  * per-stage model latency (p50/p95) and token counts
  * investigation time per step (p50/p95) and model calls per step
  * cost per full plant audit = GPU-hours used x CROMO_GPU_PRICE_PER_HOUR
  * evaluation against the planted ground truth (writes data/recorded/eval_amd.json)
and saves every investigation's event stream to data/recorded/runs/<step>.json (used by demo replay).

  CROMO_PROVIDER=amd python scripts/benchmark_amd.py [--skip-ingest] [--steps ALK-04 SOL-02] [--rocm-smi FILE]

Writes data/recorded/benchmark_amd.json (read by the System page and README).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

from cromo import archive, config, db, ingest, investigate, llm, system  # noqa: E402


def cer(hyp: str, ref: str) -> float:
    """Character error rate (Levenshtein distance / reference length) on whitespace-normalised text."""
    h, r = " ".join(hyp.split()).lower(), " ".join(ref.split()).lower()
    if not r:
        return 0.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hc in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc))
        prev = cur
    return prev[-1] / len(r)


def vision_accuracy() -> dict:
    rows = db.q("SELECT p.acc, p.page, p.lines_json FROM pages p WHERE p.source='vision'")
    scores = []
    for r in rows:
        data = archive.page_path(r["acc"], r["page"]).read_bytes()
        ref_p = config.settings.fixtures_dir / "vision" / f"{hashlib.sha256(data).hexdigest()}.json"
        if not ref_p.exists():
            continue
        ref = " ".join(x["text"] for x in json.loads(ref_p.read_text(encoding="utf-8"))["lines"])
        hyp = " ".join(x["text"] for x in json.loads(r["lines_json"]))
        scores.append({"acc": r["acc"], "page": r["page"], "cer": round(cer(hyp, ref), 4)})
    vals = [s["cer"] for s in scores]
    return {"pages": len(vals), "mean_cer": round(statistics.mean(vals), 4) if vals else None,
            "median_cer": round(statistics.median(vals), 4) if vals else None,
            "worst": sorted(scores, key=lambda s: -s["cer"])[:5],
            "note": "CER vs. the generator's reference transcription of each scanned page (lower is better)."}


def gpu_info(path: str | None) -> dict | None:
    if path:
        return {"source": f"rocm-smi output ({Path(path).name})", "summary": Path(path).read_text(encoding="utf-8")[:4000]}
    exe = shutil.which("rocm-smi")
    if exe:
        out = subprocess.run([exe, "--showmeminfo", "vram", "--showuse", "--showproductname"], capture_output=True, text=True, timeout=10)
        return {"source": "rocm-smi (benchmark host)", "summary": out.stdout[:4000]}
    return None


async def run(args):
    s = config.settings
    if not s.is_live:
        sys.exit("Live AMD mode is not configured. Set CROMO_PROVIDER=amd and the CROMO_*_BASE_URL/MODEL variables, then run "
                 "scripts/check_amd.py first.")
    started = time.time()
    db.ex("DELETE FROM metrics")
    from cromo import veteran

    veteran.purge()  # testimony recorded in demos must not influence measured results
    out: dict = {"started_at": started, "provider": "amd", "route": s.amd_route, "hardware": s.hardware_label,
                 "models": {r: llm.model_name(r) for r in ("reasoner", "vision", "embeddings")}}

    # 1. ingestion -----------------------------------------------------------
    t_ingest = 0.0
    if not args.skip_ingest:
        print("[bench] ingesting the archive on AMD ...", flush=True)
        t0 = time.perf_counter()
        st = await ingest.ingest_all(force=True, progress=lambda i, n, a: print(f"  {i}/{n}", flush=True) if i % 25 == 0 else None)
        t_ingest = time.perf_counter() - t0
        vis = [m for m in system.latency_stats("amd") if m["stage"] == "vision.transcribe"]
        scanned = st["scanned_pages"]
        vis_calls = sum(m["calls"] for m in vis)
        out["ingest"] = {
            "documents": st["documents"], "pages": st["pages"], "scanned_pages": scanned, "seconds": round(t_ingest, 1),
            "pages_per_min": round(st["pages"] / t_ingest * 60, 1),
            "scanned_pages_per_min": round(scanned / t_ingest * 60, 1) if scanned else None,
            "vision_p50_ms_per_page": vis[0]["p50_ms"] if vis else None, "vision_calls": vis_calls,
            "concurrency": s.max_concurrency,
        }
        out["vision_accuracy"] = vision_accuracy()
        print("[bench] ingest:", out["ingest"], flush=True)

    # 2. investigations (recorded for replay) ---------------------------------
    steps = args.steps or [x["id"] for x in archive.steps()]
    runs_dir = s.recorded_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    durations, calls_before = [], db.q1("SELECT COUNT(*) n FROM metrics WHERE role='reasoner'")["n"]
    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.perf_counter()

    async def one(sid):
        async with sem:
            events = []

            async def emit(ev):
                events.append(ev)

            v = await investigate.investigate(sid, emit)
            durations.append(v["duration_s"])
            (runs_dir / f"{sid}.json").write_text(json.dumps({
                "step_id": sid, "recorded_at": time.time(), "provider": "amd", "hardware": s.hardware_label,
                "models": out["models"], "events": events}, ensure_ascii=False), encoding="utf-8")
            print(f"  {sid}: {v['verdict']} ({v['duration_s']}s)", flush=True)

    print(f"[bench] investigating {len(steps)} steps (concurrency {args.concurrency}) ...", flush=True)
    await asyncio.gather(*(one(x) for x in steps))
    t_inv = time.perf_counter() - t0
    calls = db.q1("SELECT COUNT(*) n FROM metrics WHERE role='reasoner'")["n"] - calls_before
    durations.sort()
    out["investigation"] = {
        "steps": len(steps), "wall_seconds": round(t_inv, 1), "p50_s": round(statistics.median(durations), 1),
        "p95_s": round(durations[min(len(durations) - 1, int(0.95 * len(durations)))], 1),
        "calls_per_step": round(calls / max(1, len(steps)), 1), "concurrency": args.concurrency,
    }
    print("[bench] investigations:", out["investigation"], flush=True)

    # 3. evaluation -------------------------------------------------------------
    if not args.steps:
        from run_eval import evaluate

        ev = await evaluate(rerun=False)
        (s.recorded_dir / "eval_amd.json").write_text(json.dumps(ev, indent=1), encoding="utf-8")
        out["eval"] = {k: ev[k] for k in ("accuracy", "fence_recall", "false_fossil_rate", "dangerous_errors")}
        out["eval"]["citation_precision"] = ev["citations"]["precision"]
        print("[bench] eval:", out["eval"], flush=True)

    # 4. latency, tokens, cost ------------------------------------------------------
    lat = system.latency_stats("amd")
    out["latency"] = lat
    out["tokens"] = {"in": sum(m["tokens_in"] for m in lat), "out": sum(m["tokens_out"] for m in lat)}
    gpu_hours = (t_ingest + t_inv) / 3600
    out["cost"] = {"gpu_hours": round(gpu_hours, 3), "price_per_gpu_hour": s.gpu_price_per_hour,
                   "per_plant_audit_usd": round(gpu_hours * s.gpu_price_per_hour, 2),
                   "basis": "wall-clock time of full ingestion + all investigations on one GPU, times the list price",
                   "price_source": s.gpu_price_source}
    out["gpu"] = gpu_info(args.rocm_smi)
    out["finished_at"] = time.time()
    p = s.recorded_dir / "benchmark_amd.json"
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    if not args.steps:
        print("snapshot:", db.export_snapshot())
    print(f"[bench] cost per plant audit: ${out['cost']['per_plant_audit_usd']} ({out['cost']['gpu_hours']} GPU-h)")
    print("written", p)
    await llm.aclose()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--steps", nargs="*")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--rocm-smi", help="file with rocm-smi output captured on the GPU host")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
