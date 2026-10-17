"""Regenerate the README results table from measured files (never typed by hand).

  python scripts/update_readme.py

Reads data/recorded/eval_fixture.json, eval_amd.json and benchmark_amd.json.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "data" / "recorded"


def load(name):
    p = REC / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x):
    return "–" if x is None else f"{round(x * 100)}%"


def pct1(x):
    return "–" if x is None else f"{x * 100:.1f}%"


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
        use = bench.get("tokenfactory_usage") or {}
        if cost.get("per_plant_audit_usd") is not None:
            audit = f"${cost['per_plant_audit_usd']} ({cost.get('gpu_hours')} GPU-h)"
        elif use and bench.get("complete") is not False:
            audit = (f"${use['metered_usd']:.2f} on the Token Factory meter ({use['requests']} requests, "
                     f"{use['tokens'] / 1e6:.1f}M tokens; free during the event)")
        else:
            audit = "audit cost n/a (" + ("partial run" if bench.get("complete") is False else "no per-GPU billing") + ")"
        vis = f" · CER {pct1(va.get('mean_cer'))}" if va.get("mean_cer") is not None else " · recorded transcriptions"
        p50 = inv.get("p50_s")
        med = "–" if p50 is None else (f"{p50:.0f} s" if p50 < 120 else f"{p50 / 60:.0f} min")
        rows += [f"{ing.get('pages_per_min', '–')} pages/min{vis}", f"{med} · {audit}"]
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # the Windows console code page cannot print every character used here
    fx, amd, bench = load("eval_fixture.json"), load("eval_amd.json"), load("benchmark_amd.json")
    labels = ["FENCE recall", "False-FOSSIL rate", "Fences called fossils", "Accuracy, 4 classes", "Citation precision",
              "Tripwire effects found", "Change-check decisions correct", "Prompt-injection test",
              "Ingestion throughput / VLM transcription CER", "Median investigation time / cost per full plant audit"]
    a = col(fx, None, True)
    hw = (bench or {}).get("hardware", "AMD") if bench else "AMD"
    if (bench or {}).get("route") == "tokenfactory":
        hw = "the AMD Token Factory"
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
    if bench and bench.get("degraded_steps"):
        lines += ["", f"*{len(bench['degraded_steps'])} step(s) still had failed model calls on the shared endpoint after "
                  f"retries ({', '.join(bench['degraded_steps'])}); their verdicts count as measured.*"]
    if bench and (bench.get("ingest") or {}).get("note"):
        lines += ["", f"*{bench['ingest']['note']}*"]
    if bench and (bench.get("ingest") or {}).get("reused_note"):
        lines += ["", f"*{bench['ingest']['reused_note']}*"]
    oc = load("ocr_comparison.json")
    if oc:  # which AMD-hosted model reads the scans best (scripts/compare_models.py ocr)
        kinds = list(oc["models"][0]["cer_by_kind"])
        lines += ["", f"**Reading the scans: {len(oc['models'])} AMD-hosted models on the same {oc['models'][0]['pages']} scanned "
                  "pages** (character error rate vs. the reference, lower is better; word F1 ignores reading order):", "",
                  "| Model | Strict CER | Word F1 | " + " | ".join(f"{k} (n={oc['models'][0]['pages_by_kind'][k]})" for k in kinds)
                  + " | p50 / page | Failures |", "|---|---|---|" + "---|" * len(kinds) + "---|---|"]
        for m in oc["models"]:
            used = " (CROMO)" if m["model"] == (bench or {}).get("models", {}).get("vision") else ""
            lines.append(f"| `{m['model']}`{used} | {pct1(m['mean_cer'])} | {pct1(m.get('mean_word_f1'))} | "
                         + " | ".join(pct1(m["cer_by_kind"].get(k)) for k in kinds)
                         + f" | {m['p50_ms'] / 1000:.0f} s | {m['failures']}/{m['pages']} |")
    rv = load("retrieval_eval.json")
    if rv:
        a_, b_ = rv["without_expansion"], rv["with_expansion"]
        lines += ["", f"**Retrieval without an embedding model** ({b_['steps']} steps, searching with the step text): Gemma's "
                  f"bilingual keywords rank the first key document higher (mean reciprocal rank {a_['mrr']:.2f} → {b_['mrr']:.2f}); "
                  f"the share of key documents in the top 5 / top 10 stays {pct(a_['recall_at_5'])} → {pct(b_['recall_at_5'])} / "
                  f"{pct(a_['recall_at_10'])} → {pct(b_['recall_at_10'])}."]
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
