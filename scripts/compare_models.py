"""Quality tests of vision / OCR models on AMD, on the archive's scanned, faxed and handwritten pages.

  python scripts/compare_models.py vision
      Own vLLM route: model A = CROMO_VISION_* (default Gemma 4), model B = CROMO_VISION_ALT_* (Qwen2.5-VL-7B).
      Writes data/recorded/vision_comparison.json.

  python scripts/compare_models.py ocr [--models M1 M2 ...] [--limit N] [--estimate]
      AMD Token Factory route: any number of catalogue models on the same pages. Vision-language models get CROMO's
      production transcription prompt through /chat/completions; MinerU2.5-Pro (a document parser) gets the page
      through its own /ocr endpoint and returns Markdown. Each page result is cached in data/runtime/ocr_cache, so an
      interrupted or rate-limited run continues where it stopped. Writes data/recorded/ocr_comparison.json.

Measures character error rate (CER) against the reference transcription of each page, split by page type
(handwritten / typed / fax), plus latency and failures. Before scoring, Markdown syntax and CROMO's [stamp] /
[handwritten note] / [illegible] markers are removed from both sides, so a model is not penalised for formatting.
Never invents numbers: if a model fails on a page, it is reported as a failure.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import httpx  # noqa: E402

from benchmark_amd import cer, normalize  # noqa: E402
from cromo import archive, config, llm  # noqa: E402


def endpoint(prefix: str) -> dict | None:
    base, model = os.environ.get(prefix + "BASE_URL", "").rstrip("/"), os.environ.get(prefix + "MODEL", "")
    if not base or not model:
        return None
    return {"base": base, "model": model, "key": os.environ.get(prefix + "API_KEY", "")}


def page_kind(lines: list[dict]) -> str:
    text = " ".join(x["text"] for x in lines).lower()
    if "turno" in text or "f. bellone" in text:
        return "handwritten logbook"
    if "from:" in text[:80] and "p.01" in text[:200]:
        return "fax"
    if "[handwritten note]" in text:
        return "typed + handwritten note"
    return "typed / scanned"


def scanned_pages() -> list[tuple]:
    pages = []
    for acc in archive.list_accessions():
        if archive.text_layer(acc):
            continue
        for k in range(1, archive.page_count(acc) + 1):
            data = archive.page_path(acc, k).read_bytes()
            ref_p = config.settings.fixtures_dir / "vision" / f"{hashlib.sha256(data).hexdigest()}.json"
            if ref_p.exists():
                lines = json.loads(ref_p.read_text(encoding="utf-8"))["lines"]
                pages.append((acc, k, data, " ".join(x["text"] for x in lines), page_kind(lines)))
    return pages


def score(hyp: str | None, ref: str) -> float | None:
    """Strict CER: reading order matters (a block moved to the end counts as deleted and re-inserted)."""
    return round(cer(normalize(hyp), normalize(ref, markdown=False)), 4) if hyp is not None else None


def word_f1(hyp: str | None, ref: str) -> float | None:
    """Order-insensitive content accuracy: F1 of the multisets of words (case-insensitive). A model that reads every
    word but lays the page out in a different block order (e.g. letterhead last) scores high here and low on CER."""
    if hyp is None:
        return None
    from collections import Counter

    h, r = Counter(normalize(hyp).lower().split()), Counter(normalize(ref, markdown=False).lower().split())
    common = sum((h & r).values())
    if not h or not r or not common:
        return 0.0
    p, rc = common / sum(h.values()), common / sum(r.values())
    return round(2 * p * rc / (p + rc), 4)


def summary(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["ok"]]
    by, f1_by, n_by = {}, {}, {}
    for kind in sorted({r["kind"] for r in rows}):
        v = [r["cer"] for r in ok if r["kind"] == kind]
        f = [r["word_f1"] for r in ok if r["kind"] == kind and r.get("word_f1") is not None]
        by[kind] = round(statistics.mean(v), 4) if v else None
        f1_by[kind] = round(statistics.mean(f), 4) if f else None
        n_by[kind] = sum(1 for r in rows if r["kind"] == kind)
    f1 = [r["word_f1"] for r in ok if r.get("word_f1") is not None]
    return {"pages": len(rows), "failures": len(rows) - len(ok),
            "mean_cer": round(statistics.mean([r["cer"] for r in ok]), 4) if ok else None,
            "median_cer": round(statistics.median([r["cer"] for r in ok]), 4) if ok else None,
            "mean_word_f1": round(statistics.mean(f1), 4) if f1 else None,
            "cer_by_kind": by, "word_f1_by_kind": f1_by, "pages_by_kind": n_by,
            "p50_ms": round(statistics.median([r["ms"] for r in ok])) if ok else None,
            "p95_ms": round(sorted(r["ms"] for r in ok)[min(len(ok) - 1, int(0.95 * len(ok)))]) if ok else None}


async def transcribe(c: httpx.AsyncClient, ep: dict, data: bytes) -> tuple[str | None, float]:
    body = {"model": ep["model"], "max_tokens": 1800, "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/webp;base64," + base64.b64encode(data).decode()}},
        {"type": "text", "text": llm.VISION_PROMPT}]}]}
    t0 = time.perf_counter()
    try:
        r = await c.post(ep["base"] + "/chat/completions", json=body,
                         headers={"Authorization": f"Bearer {ep['key']}"} if ep["key"] else {})
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code >= 400:
            return None, ms
        txt = r.json()["choices"][0]["message"].get("content") or ""
        return llm._THINK.sub("", txt).strip(), ms
    except httpx.HTTPError:
        return None, (time.perf_counter() - t0) * 1000


async def vision():
    a, b = endpoint("CROMO_VISION_"), endpoint("CROMO_VISION_ALT_")
    if not a or not b:
        sys.exit("Set CROMO_VISION_* (model A) and CROMO_VISION_ALT_* (model B).")
    pages = scanned_pages()
    print(f"{len(pages)} scanned pages; A={a['model']}  B={b['model']}")
    sem = asyncio.Semaphore(8)
    results = {"A": [], "B": []}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=20)) as c:
        async def one(tag, ep, acc, k, data, ref, kind):
            async with sem:
                txt, ms = await transcribe(c, ep, data)
                results[tag].append({"acc": acc, "page": k, "kind": kind, "ok": txt is not None, "ms": round(ms),
                                     "cer": score(txt, ref)})
        await asyncio.gather(*(one(t, ep, *p) for t, ep in (("A", a), ("B", b)) for p in pages))

    out = {"task": "transcribe scanned / faxed / handwritten archive pages", "measured_at": time.time(),
           "hardware": config.settings.hardware_label,
           "A": {"model": a["model"], **summary(results["A"])}, "B": {"model": b["model"], **summary(results["B"])},
           "note": "CER = character error rate vs. the reference transcription (lower is better). Same prompt, same images.",
           "pages": results}
    sa, sb = out["A"], out["B"]
    if sa["mean_cer"] is not None and sb["mean_cer"] is not None:
        better = "A" if sa["mean_cer"] <= sb["mean_cer"] else "B"
        out["verdict"] = (f"{out[better]['model']} reads the archive more accurately "
                          f"(mean CER {sa['mean_cer']:.1%} vs {sb['mean_cer']:.1%}).")
    p = config.settings.recorded_dir / "vision_comparison.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for tag in ("A", "B"):
        s = out[tag]
        print(f"  {tag} {s['model']}: mean CER {s['mean_cer']}, by kind {s['cer_by_kind']}, p50 {s['p50_ms']} ms, failures {s['failures']}")
    print(out.get("verdict", "no verdict (a model failed)"))
    print("written", p)


# ---------------------------------------------------------------------------------------------- Token Factory OCR
OCR_MODELS = ["Gemma-4-31B-IT", "MinerU2.5-Pro", "DeepSeek-V4-Flash-Vision-Exp", "MiniCPM-V-4.7-35B-A3B"]
OCR_ENDPOINT_MODELS = {"MinerU2.5-Pro"}  # document parsers served on POST /v1/ocr instead of chat


def _png(data: bytes) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def _cache_file(model: str, acc: str, page: int) -> Path:
    return config.settings.runtime_dir / "ocr_cache" / re.sub(r"[^\w.-]", "_", model) / f"{acc}-p{page}.json"


async def _ocr_call(c: httpx.AsyncClient, model: str, data: bytes) -> dict:
    """One page through one model. Returns {ok, text, ms, error?, tokens?}; retries 429/5xx with Retry-After."""
    if model in OCR_ENDPOINT_MODELS:
        path = "/ocr"
        body = {"model": model, "document": {"type": "image_url",
                                             "image_url": "data:image/png;base64," + base64.b64encode(_png(data)).decode()}}
    else:
        path = "/chat/completions"
        body = {"model": model, "max_tokens": 1800, "temperature": 0, "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/webp;base64," + base64.b64encode(data).decode()}},
            {"type": "text", "text": llm.VISION_PROMPT}]}]}
    limiter = llm._limiter(config.settings.vision)
    err = ""
    for attempt in range(6):
        if limiter:
            await limiter.acquire()
        t0 = time.perf_counter()
        try:
            r = await c.post(path, json=body)
        except httpx.HTTPError as e:
            err = type(e).__name__
            await asyncio.sleep(3 * (attempt + 1))
            continue
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code in (429, 500, 502, 503, 504):
            err = f"HTTP {r.status_code}"
            wait = llm._retry_after(r, attempt)
            if r.status_code == 429 and limiter:
                limiter.backoff(wait)
            await asyncio.sleep(wait)
            continue
        if r.status_code >= 400:
            return {"ok": False, "text": None, "ms": round(ms), "error": f"HTTP {r.status_code}: {llm._error_text(r)[:160]}"}
        j = r.json()
        if path == "/ocr":
            text = "\n".join(p.get("markdown") or "" for p in j.get("pages") or [])
            return {"ok": True, "text": text, "ms": round(ms),
                    "pages_processed": (j.get("usage_info") or {}).get("pages_processed")}
        ch = j["choices"][0]
        text = llm._THINK.sub("", ch["message"].get("content") or "").strip()
        u = j.get("usage") or {}
        if not text:
            return {"ok": False, "text": None, "ms": round(ms), "error": f"empty answer (finish_reason={ch.get('finish_reason')})"}
        return {"ok": True, "text": text, "ms": round(ms), "finish": ch.get("finish_reason"),
                "tokens_in": u.get("prompt_tokens"), "tokens_out": u.get("completion_tokens"), "cost": u.get("cost")}
    return {"ok": False, "text": None, "ms": None, "error": err or "failed"}


async def ocr(models: list[str], limit: int | None, estimate: bool, retry_failed: bool = False) -> None:
    s = config.settings
    role = s.vision if s.vision.configured else s.reasoner
    if not role.base_url:
        sys.exit("Configure the Token Factory first (CROMO_AMD_ROUTE=tokenfactory and AMD_TOKEN_FACTORY in .env).")
    pages = scanned_pages()
    pages = pages[:limit] if limit else pages
    retried = 0
    if retry_failed:  # one more attempt for pages that failed with a transient error; the count is reported
        for m in models:
            for p in pages:
                f = _cache_file(m, p[0], p[1])
                if f.exists() and not json.loads(f.read_text(encoding="utf-8"))["ok"]:
                    f.unlink()
                    retried += 1
    todo = [(m, p) for m in models for p in pages if not _cache_file(m, p[0], p[1]).exists()]
    rpm = s.rpm_limit or 60
    print(f"{len(pages)} scanned pages x {len(models)} models = {len(pages) * len(models)} page reads; "
          f"{len(todo)} not cached yet -> at least {len(todo) / rpm:.0f} min at {rpm} requests/min", flush=True)
    if estimate:
        return
    sem = asyncio.Semaphore(s.max_concurrency)
    headers = {"Authorization": f"Bearer {role.api_key}"} if role.api_key else {}
    done = 0
    async with httpx.AsyncClient(base_url=role.base_url, headers=headers, verify=llm._ssl_context(),
                                 timeout=httpx.Timeout(600, connect=20)) as c:
        async def one(model, page):
            nonlocal done
            acc, k, data, ref, kind = page
            async with sem:
                res = await _ocr_call(c, model, data)
            res.update({"acc": acc, "page": k, "kind": kind, "model": model, "measured_at": time.time()})
            f = _cache_file(model, acc, k)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            done += 1
            print(f"  [{done}/{len(todo)}] {model:30s} {acc} p{k} {kind:24s} "
                  + (f"CER {score(res['text'], ref):.3f} {res['ms']} ms" if res["ok"] else f"FAIL {res.get('error')}"),
                  flush=True)

        # interleave models so a slow model (MinerU) never holds every slot at once
        order = sorted(todo, key=lambda mp: (pages.index(mp[1]), models.index(mp[0])))
        await asyncio.gather(*(one(m, p) for m, p in order))

    results = {}
    for m in models:
        rows = []
        for acc, k, _, ref, kind in pages:
            res = json.loads(_cache_file(m, acc, k).read_text(encoding="utf-8"))
            rows.append({"acc": acc, "page": k, "kind": kind, "ok": res["ok"], "ms": res.get("ms"),
                         "cer": score(res.get("text"), ref), "word_f1": word_f1(res.get("text"), ref),
                         "error": res.get("error")})
        results[m] = rows
    sums = {m: summary(results[m]) for m in models}
    ranked = sorted((m for m in models if sums[m]["mean_cer"] is not None), key=lambda m: sums[m]["mean_cer"])
    out = {"task": "transcribe scanned / faxed / handwritten archive pages", "measured_at": time.time(),
           "route": s.amd_route, "hardware": s.hardware_label,
           "models": [{"model": m, "interface": "/v1/ocr (Markdown)" if m in OCR_ENDPOINT_MODELS else "/v1/chat/completions",
                       **sums[m]} for m in models],
           "ranking": ranked, "retried_failed_pages": retried or None,
           "note": ("CER = character error rate vs. the generator's reference transcription (lower is better), after removing "
                    "Markdown syntax and the [stamp]/[handwritten note]/[illegible] markers; it counts reading order. Word F1 = "
                    "order-insensitive share of words read correctly (higher is better). Same page images for every model; "
                    "chat models get CROMO's production transcription prompt. Latency is per page on the shared Token Factory "
                    "(it includes queueing on AMD's side). Small samples per page type: see pages_by_kind."),
           "pages": results}
    p = s.recorded_dir / "ocr_comparison.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print()
    for row in out["models"]:
        print(f"  {row['model']:30s} mean CER {row['mean_cer']}  word F1 {row['mean_word_f1']}  by kind {row['cer_by_kind']}  "
              f"p50 {row['p50_ms']} ms  failures {row['failures']}/{row['pages']}")
    print("ranking (best first):", ranked)
    print("written", p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["vision", "ocr"])
    ap.add_argument("--models", nargs="*", default=OCR_MODELS)
    ap.add_argument("--limit", type=int, help="only the first N scanned pages (quick test)")
    ap.add_argument("--estimate", action="store_true", help="print the number of calls and minimum time, then stop")
    ap.add_argument("--retry-failed", action="store_true", help="re-run pages that failed (e.g. HTTP 500) once")
    a = ap.parse_args()
    asyncio.run(vision() if a.what == "vision" else ocr(a.models, a.limit, a.estimate, a.retry_failed))
