"""A/B quality test of two vision models on AMD, on the archive's scanned, faxed and handwritten pages.

  python scripts/compare_models.py vision

Model A = CROMO_VISION_* (default Gemma 4), model B = CROMO_VISION_ALT_* (default Qwen2.5-VL-7B).
Both get the same prompt and image. Measures character error rate (CER) against the reference transcription of each
page, split by page type (handwritten / typed / fax), plus latency and failures.
Writes data/recorded/vision_comparison.json (shown on the System page and in the README). Never invents numbers:
if a model fails, it is reported as a failure.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import httpx  # noqa: E402

from benchmark_amd import cer  # noqa: E402
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
    return "typed / scanned"


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
    print(f"{len(pages)} scanned pages; A={a['model']}  B={b['model']}")
    sem = asyncio.Semaphore(8)
    results = {"A": [], "B": []}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=20)) as c:
        async def one(tag, ep, acc, k, data, ref, kind):
            async with sem:
                txt, ms = await transcribe(c, ep, data)
                results[tag].append({"acc": acc, "page": k, "kind": kind, "ok": txt is not None, "ms": round(ms),
                                     "cer": round(cer(txt, ref), 4) if txt is not None else None})
        await asyncio.gather(*(one(t, ep, *p) for t, ep in (("A", a), ("B", b)) for p in pages))

    def summary(rows):
        ok = [r for r in rows if r["ok"]]
        by = {}
        for kind in sorted({r["kind"] for r in rows}):
            v = [r["cer"] for r in ok if r["kind"] == kind]
            by[kind] = round(statistics.mean(v), 4) if v else None
        return {"pages": len(rows), "failures": len(rows) - len(ok),
                "mean_cer": round(statistics.mean([r["cer"] for r in ok]), 4) if ok else None,
                "median_cer": round(statistics.median([r["cer"] for r in ok]), 4) if ok else None,
                "cer_by_kind": by, "p50_ms": round(statistics.median([r["ms"] for r in ok])) if ok else None}

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


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "vision":
        sys.exit(__doc__)
    asyncio.run(vision())
