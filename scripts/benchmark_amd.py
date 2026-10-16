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
  ... --resume            continue an interrupted run (progress is saved after the ingest and after every step)
  ... --finalize-partial  publish what an interrupted run measured, clearly marked partial (no eval score, no audit cost)

Writes data/recorded/benchmark_amd.json (read by the System page and README).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

from cromo import archive, config, db, ingest, investigate, llm, system, tokenfactory  # noqa: E402


_MARKERS = re.compile(r"\[(?:stamp|handwritten note|illegible)\]", re.I)
_MD = [(re.compile(r"<[^>]{1,40}>"), " "), (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),
       (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""), (re.compile(r"^\s*[-*+]\s+", re.M), ""),
       (re.compile(r"^\s*\|?\s*:?-{3,}.*$", re.M), ""), (re.compile(r"\*\*|__|`"), ""), (re.compile(r"\|"), " ")]


def normalize(text: str, markdown: bool = True) -> str:
    """Text used for CER: CROMO's [stamp]/[handwritten note]/[illegible] markers removed, and (for model output)
    Markdown syntax stripped, so a model is scored on what it read rather than on formatting."""
    text = _MARKERS.sub(" ", text or "")
    if markdown:
        for rx, rep in _MD:
            text = rx.sub(rep, text)
    return " ".join(text.split())


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
        scores.append({"acc": r["acc"], "page": r["page"], "cer": round(cer(normalize(hyp), normalize(ref, False)), 4)})
    vals = [s["cer"] for s in scores]
    return {"pages": len(vals), "mean_cer": round(statistics.mean(vals), 4) if vals else None,
            "median_cer": round(statistics.median(vals), 4) if vals else None,
            "worst": sorted(scores, key=lambda s: -s["cer"])[:5],
            "note": "CER vs. the generator's reference transcription of each scanned page (lower is better), "
                    "after removing Markdown and the [stamp]/[handwritten note] markers."}


def gpu_info(path: str | None) -> dict | None:
    if path:
        return {"source": f"rocm-smi output ({Path(path).name})", "summary": Path(path).read_text(encoding="utf-8")[:4000]}
    exe = shutil.which("rocm-smi")
    if exe:
        out = subprocess.run([exe, "--showmeminfo", "vram", "--showuse", "--showproductname"], capture_output=True, text=True, timeout=10)
        return {"source": "rocm-smi (benchmark host)", "summary": out.stdout[:4000]}
    return None


def _partial_path(tag: str) -> Path:
    return config.settings.recorded_dir / f"benchmark_amd{'_' + tag if tag else ''}.partial.json"


def _save_partial(out: dict, tag: str) -> None:
    p = _partial_path(tag)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")


def _usage(out: dict) -> None:
    """Token Factory route: what the run consumed according to the platform's own meter (GET /v1/usage)."""
    before = out.pop("usage_before", None)
    after = tokenfactory.usage()
    d = tokenfactory.delta(before, after)
    if d:
        out["tokenfactory_usage"] = {**d, "daily_limit_usd": after.get("daily_cost_limit_usd"),
                                     "basis": "AMD Token Factory meter (GET /v1/usage), all-time counters before and after the "
                                              "run; free during the event (points with no monetary value). Includes any other "
                                              "use of the team key during the run."}


def _cost(s, seconds: float, complete: bool) -> dict:
    if s.amd_route == "tokenfactory":  # shared serving: our GPU time is not observable, so no audit cost is claimed
        return {"gpu_hours": None, "price_per_gpu_hour": None, "per_plant_audit_usd": None,
                "basis": "AMD Token Factory (shared serving, no per-GPU billing): GPU time per audit is not observable"}
    gpu_hours = seconds / 3600
    return {"gpu_hours": round(gpu_hours, 3), "price_per_gpu_hour": s.gpu_price_per_hour,
            "per_plant_audit_usd": round(gpu_hours * s.gpu_price_per_hour, 2) if complete else None,
            "basis": "wall-clock time of full ingestion + all investigations on one GPU, times the list price"
            if complete else "partial run: GPU time of the measured part only; no full-audit cost is claimed",
            "price_source": s.gpu_price_source}


def _estimate(s, args, out: dict) -> None:
    """Print the expected number of model calls and the minimum time at the endpoint's request limit."""
    n_docs = 0 if args.skip_ingest or out.get("ingest") else len(archive.list_accessions())
    scanned = sum(archive.page_count(a) for a in archive.list_accessions() if not archive.text_layer(a)) if n_docs else 0
    steps = len(args.steps or archive.steps()) - len(out.get("durations", {}))
    calls = n_docs + (scanned if s.vision.configured else 0) + steps * 9 + (0 if args.steps else 25)
    msg = f"[bench] estimate: ~{calls} model calls ({n_docs} documents, {scanned} scanned pages, {steps} steps x ~9 hops"
    msg += ", evaluation ~25)" if not args.steps else ")"
    if s.rpm_limit:
        msg += f" -> at least {calls / s.rpm_limit:.0f} min at {s.rpm_limit} requests/min"
    u = tokenfactory.usage()
    if u:
        msg += (f"; Token Factory today: {u['today']['requests']} requests, ${u['daily_cost_used_usd']:.3f} of "
                f"${u['daily_cost_limit_usd']} used (resets {u['daily_reset_at']})")
    print(msg, flush=True)


def finalize_partial(args) -> None:
    s = config.settings
    p = _partial_path(args.tag)
    if not p.exists():
        sys.exit(f"No partial run found ({p.name}).")
    out = json.loads(p.read_text(encoding="utf-8"))
    d = sorted(out.get("durations", {}).values())
    n_all = len(archive.steps())
    out["complete"] = False
    out["investigation"] = {"steps": len(d), "of_steps": n_all, "wall_seconds": round(out.get("inv_wall_s", 0.0), 1),
                            "p50_s": round(statistics.median(d), 1) if d else None,
                            "p95_s": round(d[min(len(d) - 1, int(0.95 * len(d)))], 1) if d else None,
                            "concurrency": args.concurrency}
    lat = system.latency_stats("amd")
    out["latency"] = lat
    out["tokens"] = {"in": sum(m["tokens_in"] for m in lat), "out": sum(m["tokens_out"] for m in lat)}
    out["cost"] = _cost(s, (out.get("ingest") or {}).get("seconds", 0.0) + out.get("inv_wall_s", 0.0), False)
    out["gpu"] = gpu_info(args.rocm_smi)
    out["finished_at"] = time.time()
    out["tag"] = args.tag or "primary"
    _usage(out)
    out["note"] = f"PARTIAL run: {len(d)} of {n_all} steps investigated on AMD; no evaluation score is reported for a partial run."
    for k in ("durations", "inv_wall_s"):
        out.pop(k, None)
    dest = s.recorded_dir / f"benchmark_amd{'_' + args.tag if args.tag else ''}.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(out["note"])
    print("written", dest)


async def run(args):
    s = config.settings
    if not s.is_live:
        sys.exit("Live AMD mode is not configured. Set CROMO_PROVIDER=amd and the CROMO_*_BASE_URL/MODEL variables, then run "
                 "scripts/check_amd.py first.")
    from cromo import veteran

    veteran.purge()  # testimony recorded in demos must not influence measured results
    models = {r: llm.model_name(r) for r in ("reasoner", "vision", "embeddings")}
    pp = _partial_path(args.tag)
    out: dict | None = None
    if args.resume and pp.exists():
        out = json.loads(pp.read_text(encoding="utf-8"))
        if out.get("models") != models:
            sys.exit("--resume: the configured models differ from the interrupted run; start a fresh run instead.")
        print(f"[bench] resuming: ingest {'done' if out.get('ingest') else 'pending'}, "
              f"{len(out.get('durations', {}))} step(s) already investigated", flush=True)
    if out is None:
        db.ex("DELETE FROM metrics")
        out = {"started_at": time.time(), "provider": "amd", "route": s.amd_route, "hardware": s.hardware_label,
               "models": models, "durations": {}, "inv_wall_s": 0.0, "usage_before": tokenfactory.usage()}
        _save_partial(out, args.tag)
    _estimate(s, args, out)

    # 1. ingestion (resumable per document) ------------------------------------
    t_ingest = (out.get("ingest") or {}).get("seconds", 0.0)
    if not args.skip_ingest and not out.get("ingest"):
        prog = out.setdefault("ingest_progress", {"done": [], "seconds": 0.0, "documents": 0, "pages": 0, "scanned_pages": 0})
        prog["seconds"] += prog.pop("seconds_running", 0.0)  # time spent by an interrupted run up to its last save
        all_accs = archive.list_accessions()
        todo_accs = [a for a in all_accs if a not in set(prog["done"])]
        print(f"[bench] ingesting {len(todo_accs)} of {len(all_accs)} documents on AMD ...", flush=True)
        t0 = time.perf_counter()

        def progress(i, n, acc):
            prog["done"].append(acc)
            pages = archive.page_count(acc)
            prog["documents"] += 1
            prog["pages"] += pages
            prog["scanned_pages"] += 0 if archive.text_layer(acc) else pages
            if i % 10 == 0 or i == n:
                prog["seconds_running"] = time.perf_counter() - t0
                _save_partial(out, args.tag)
            if i % 25 == 0:
                print(f"  {i}/{n}", flush=True)

        st = await ingest.ingest_all(force=True, accs=todo_accs, progress=progress, tolerate_failures=True)
        for attempt in range(3):  # the shared endpoint can be overloaded for a while: pause, then retry what failed
            if not st["failed"]:
                break
            print(f"[bench] {len(st['failed'])} document(s) failed ({', '.join(st['failed'][:5])}); retrying in 90 s", flush=True)
            await asyncio.sleep(90)
            st = await ingest.ingest_all(force=True, accs=st["failed"], progress=progress, tolerate_failures=True)
        prog["seconds"] += time.perf_counter() - t0
        prog.pop("seconds_running", None)
        if st["failed"]:
            _save_partial(out, args.tag)
            sys.exit(f"[bench] {len(st['failed'])} document(s) still fail on the endpoint: {st['failed']}. "
                     "Progress is saved; rerun with --resume when the endpoint recovers.")
        t_ingest = prog["seconds"]
        vis = [m for m in system.latency_stats("amd") if m["stage"] == "vision.transcribe"]
        scanned = prog["scanned_pages"]
        vis_calls = sum(m["calls"] for m in vis)
        out["ingest"] = {
            "documents": prog["documents"], "pages": prog["pages"], "scanned_pages": scanned, "seconds": round(t_ingest, 1),
            "pages_per_min": round(prog["pages"] / t_ingest * 60, 1),
            "scanned_pages_per_min": round(scanned / t_ingest * 60, 1) if scanned else None,
            "vision_p50_ms_per_page": vis[0]["p50_ms"] if vis else None, "vision_calls": vis_calls,
            "concurrency": s.max_concurrency, "rpm_limit": s.rpm_limit or None,
        }
        if s.rpm_limit:
            out["ingest"]["note"] = (f"Throughput is bounded by the endpoint's request limit ({s.rpm_limit} requests/min on our "
                                     "side), not by the GPU: each document costs one model call, each scanned page one more.")
        out.pop("ingest_progress", None)
        if s.vision.configured:
            out["vision_accuracy"] = vision_accuracy()
        else:  # recorded transcriptions were used: their "accuracy" would be meaningless, so none is reported
            out["ingest"]["scanned_pages_per_min"] = None
            out["vision_accuracy"] = {"pages": 0, "mean_cer": None, "median_cer": None, "worst": [],
                                      "note": "No AMD vision model configured: scanned pages used recorded transcriptions (not measured)."}
        print("[bench] ingest:", out["ingest"], flush=True)
        _save_partial(out, args.tag)

    # 2. investigations (recorded for replay) ---------------------------------
    steps = args.steps or [x["id"] for x in archive.steps()]
    runs_dir = s.recorded_dir / ("runs" if not args.tag else f"runs_{args.tag}")
    runs_dir.mkdir(parents=True, exist_ok=True)
    done: dict = out["durations"]
    todo = [x for x in steps if x not in done]
    prior_wall = out.get("inv_wall_s", 0.0)
    calls_before = db.q1("SELECT COUNT(*) n FROM metrics WHERE role='reasoner'")["n"]
    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.perf_counter()

    degraded: dict[str, int] = {}

    async def one(sid):
        async with sem:
            for attempt in range(3):
                events = []

                async def emit(ev):
                    events.append(ev)

                v = await investigate.investigate(sid, emit)
                errs = (v.get("stats") or {}).get("provider_errors", 0)
                if not errs:
                    degraded.pop(sid, None)
                    break
                # a model call failed on the endpoint (not a model judgement): repeat the whole investigation later
                degraded[sid] = errs
                print(f"  {sid}: {errs} failed model call(s) on the endpoint; retrying in 60 s", flush=True)
                await asyncio.sleep(60)
            done[sid] = v["duration_s"]
            (runs_dir / f"{sid}.json").write_text(json.dumps({
                "step_id": sid, "recorded_at": time.time(), "provider": "amd", "hardware": s.hardware_label,
                "models": out["models"], "events": events}, ensure_ascii=False), encoding="utf-8")
            out["inv_wall_s"] = prior_wall + (time.perf_counter() - t0)
            _save_partial(out, args.tag)
            print(f"  {sid}: {v['verdict']} ({v['duration_s']}s)", flush=True)

    print(f"[bench] investigating {len(todo)} of {len(steps)} steps (concurrency {args.concurrency}) ...", flush=True)
    await asyncio.gather(*(one(x) for x in todo))
    if degraded:
        out["degraded_steps"] = degraded
        _save_partial(out, args.tag)
        print(f"[bench] WARNING: {len(degraded)} step(s) still had failed model calls after retries: {degraded}. "
              "They are reported in benchmark_amd.json (degraded_steps).", flush=True)
    t_inv = prior_wall + (time.perf_counter() - t0)
    calls = db.q1("SELECT COUNT(*) n FROM metrics WHERE role='reasoner'")["n"] - calls_before
    durations = sorted(done[x] for x in steps if x in done)
    out["investigation"] = {
        "steps": len(steps), "wall_seconds": round(t_inv, 1), "p50_s": round(statistics.median(durations), 1),
        "p95_s": round(durations[min(len(durations) - 1, int(0.95 * len(durations)))], 1),
        "calls_per_step": round(calls / max(1, len(todo)), 1), "concurrency": args.concurrency,
    }
    print("[bench] investigations:", out["investigation"], flush=True)

    # 3. evaluation -------------------------------------------------------------
    if not args.steps:
        from run_eval import evaluate

        ev = await evaluate(rerun=False)
        (s.recorded_dir / f"eval_amd{'_' + args.tag if args.tag else ''}.json").write_text(json.dumps(ev, indent=1), encoding="utf-8")
        out["eval"] = {k: ev[k] for k in ("accuracy", "fence_recall", "false_fossil_rate", "dangerous_errors")}
        out["eval"]["citation_precision"] = ev["citations"]["precision"]
        print("[bench] eval:", out["eval"], flush=True)

    # 4. latency, tokens, cost ------------------------------------------------------
    lat = system.latency_stats("amd")
    out["latency"] = lat
    out["tokens"] = {"in": sum(m["tokens_in"] for m in lat), "out": sum(m["tokens_out"] for m in lat)}
    full = not args.steps and not args.skip_ingest
    out["cost"] = _cost(s, t_ingest + t_inv, full)
    out["complete"] = full
    if not full:
        n_all = len(archive.steps())
        out["investigation"]["of_steps"] = n_all
        out["note"] = (f"PARTIAL run: {len(steps)} of {n_all} steps investigated on AMD"
                       + ("" if not args.skip_ingest else ", ingest not re-measured") + "; no evaluation score is reported.")
    for k in ("durations", "inv_wall_s"):
        out.pop(k, None)
    out["gpu"] = gpu_info(args.rocm_smi)
    out["finished_at"] = time.time()
    out["tag"] = args.tag or "primary"
    _usage(out)
    p = s.recorded_dir / f"benchmark_amd{'_' + args.tag if args.tag else ''}.json"
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    _partial_path(args.tag).unlink(missing_ok=True)
    if not args.steps and not args.tag:
        print("snapshot:", db.export_snapshot())
    print(f"[bench] cost per plant audit: {out['cost']['per_plant_audit_usd']} USD ({out['cost']['gpu_hours']} GPU-h)")
    print("written", p)
    await llm.aclose()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--steps", nargs="*")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--rocm-smi", help="file with rocm-smi output captured on the GPU host")
    ap.add_argument("--tag", default="", help="secondary A/B run (e.g. qwen): results go to *_<tag>.json; no replays/snapshot")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted run from its saved progress")
    ap.add_argument("--finalize-partial", action="store_true", help="publish an interrupted run's measurements, marked partial")
    a = ap.parse_args()
    if a.finalize_partial:
        finalize_partial(a)
    else:
        asyncio.run(run(a))


if __name__ == "__main__":
    main()
