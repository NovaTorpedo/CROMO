"""Regenerate the README results table from measured files (never typed by hand).

  python scripts/update_readme.py

Reads data/recorded/eval_fixture.json, eval_amd.json and benchmark_amd.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "data" / "recorded"


def load(name):
    p = REC / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x):
    return "–" if x is None else f"{round(x * 100)}%"


def col(ev: dict | None, bench: dict | None, baseline: bool) -> list[str]:
    if not ev and (baseline or not bench):
        return ["*pending AMD benchmark*"] + ["*pending*"] * 9
    if not ev:  # partial AMD run: throughput and latency were measured, the evaluation was not
        rows = ["*not scored (partial run)*"] * 8
    else:
        rows = _eval_rows(ev)
    if baseline or not bench:
        rows += ["n/a (recorded transcriptions)" if baseline else "*pending*", "n/a" if baseline else "*pending*"]
    else:
        ing, va, inv, cost = bench.get("ingest") or {}, bench.get("vision_accuracy") or {}, bench.get("investigation") or {}, bench.get("cost") or {}
        audit = (f"${cost['per_plant_audit_usd']} ({cost.get('gpu_hours')} GPU-h)" if cost.get("per_plant_audit_usd") is not None
                 else "audit cost n/a (" + ("partial run" if bench.get("complete") is False else "Token Factory, no per-GPU billing") + ")")
        rows += [f"{ing.get('pages_per_min', '–')} pages/min · CER {pct(va.get('mean_cer'))}",
                 f"{inv.get('p50_s', '–')} s · {audit}"]
    return rows


def _eval_rows(ev: dict) -> list[str]:
    dang = ev["dangerous_errors"]
    return [
        pct(ev["fence_recall"]), pct(ev["false_fossil_rate"]),
        f"{len(dang)}" + (f" ({', '.join(dang)})" if dang else ""),
        pct(ev["accuracy"]), pct(ev["citations"]["precision"]),
        f"{pct(ev['tripwires']['recall'])} of {ev['tripwires']['expected_effects']}",
        f"{pct(ev['change_checks']['accuracy'])} of {len(ev['change_checks']['cases'])}",
        "passed" if ev["injection"]["passed"] else "**failed**",
    ]


def main():
    fx, amd, bench = load("eval_fixture.json"), load("eval_amd.json"), load("benchmark_amd.json")
    labels = ["FENCE recall", "False-FOSSIL rate", "Fences called fossils", "Accuracy, 4 classes", "Citation precision",
              "Tripwire effects found", "Change-check decisions correct", "Prompt-injection test",
              "Ingestion throughput / VLM transcription CER", "Median investigation time / cost per full plant audit"]
    a = col(fx, None, True)
    hw = (bench or {}).get("hardware", "AMD MI300X") if bench else "AMD MI300X"
    model = ((amd or {}).get("models") or {}).get("reasoner", "")
    b = col(amd, bench, False)
    head = f"| | Rule-based baseline (offline fixture provider, no LLM) | CROMO on {hw}{(' · ' + model) if model else ''} |"
    lines = [head, "|---|---|---|"] + [f"| {lab} | {x} | {y} |" for lab, x, y in zip(labels, a, b)]
    vc = load("vision_comparison.json")
    if vc:  # measured Gemma-vs-alternative reading quality, same pages, same GPU
        lines += ["", "**Vision A/B on AMD** (character error rate on the archive's scanned pages, lower is better):", "",
                  "| Model | Mean CER | p50 latency | Failures |", "|---|---|---|---|"]
        lines += [f"| `{vc[t]['model']}` | {'–' if vc[t]['mean_cer'] is None else format(vc[t]['mean_cer'], '.1%')} | {vc[t]['p50_ms']} ms | {vc[t]['failures']}/{vc[t]['pages']} |" for t in ("A", "B")]
        if vc.get("verdict"):
            lines += ["", vc["verdict"]]
    alt = load("eval_amd_qwen.json")
    if amd and alt:  # optional reasoner A/B (benchmark_amd.py --tag qwen)
        lines += ["", "**Reasoner A/B on AMD** (same 49-step ground truth):", "",
                  "| Model | Accuracy | FENCE recall | False-FOSSIL rate | Dangerous errors |", "|---|---|---|---|---|"]
        lines += [f"| `{(e.get('models') or {}).get('reasoner', '')}` | {pct(e.get('accuracy'))} | {pct(e.get('fence_recall'))} | "
                  f"{pct(e.get('false_fossil_rate'))} | {len(e.get('dangerous_errors') or [])} |" for e in (amd, alt)]
    readme = ROOT / "README.md"
    s = readme.read_text(encoding="utf-8")
    s = re.sub(r"(<!-- RESULTS:START -->\n).*?(\n<!-- RESULTS:END -->)", lambda m: m.group(1) + "\n".join(lines) + m.group(2), s, flags=re.S)
    readme.write_text(s, encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
