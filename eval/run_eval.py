"""CROMO evaluation harness.

Scores the product against the planted ground truth in eval/ground_truth.json.
The product itself never reads that file; only this harness does.

  python eval/run_eval.py            # score stored verdicts, run tripwire + change-check suites
  python eval/run_eval.py --rerun    # re-investigate every step first (uses the configured provider)

Writes data/recorded/eval_<provider>.json (read by the System page and the README).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from cromo import changecheck, config, investigate, llm, tripwires  # noqa: E402

CLASSES = ["FOSSIL", "FENCE", "ACTIVE", "UNKNOWN"]


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


async def evaluate(rerun: bool = False) -> dict:
    gt = json.loads((ROOT / "eval" / "ground_truth.json").read_text(encoding="utf-8"))
    truth = gt["steps"]
    if rerun or not investigate.all_stored():
        await investigate.investigate_all(concurrency=config.settings.max_concurrency)
    vs = investigate.all_stored()
    recipe_accs = {d["accession"] for d in gt["documents"].values() if (d.get("kind") or "").startswith("recipe")}

    conf: dict[str, Counter] = defaultdict(Counter)
    per_step = []
    cite_tot = cite_ok = key_tot = key_hit = 0
    quotes_rejected = 0
    for sid, t in truth.items():
        v = vs.get(sid)
        pred = v["verdict"] if v else "MISSING"
        conf[t["label"]][pred] += 1
        cited = set()
        if v:
            for eid in v["strength"]["cited"]:
                e = v["evidence"].get(eid)
                if e and e["stance"] != "context":
                    cited.add(e["acc"])
            quotes_rejected += v.get("stats", {}).get("unverified_quotes", 0)
        relevant = set(t["key_accessions"]) | set(t["also_accessions"]) | recipe_accs
        if v and pred != "UNKNOWN":
            cite_tot += len(cited)
            cite_ok += len(cited & relevant)
        if t["label"] in ("FOSSIL", "FENCE"):
            key_tot += len(t["key_accessions"])
            key_hit += len(cited & set(t["key_accessions"]))
        per_step.append({"step": sid, "truth": t["label"], "pred": pred, "ok": pred == t["label"],
                         "strength": v["strength"]["grade"] if v else None, "tags": t["tags"],
                         "cited": sorted(cited), "irrelevant_citations": sorted(cited - relevant)})

    per_class = {}
    for c in CLASSES:
        tp = conf[c][c]
        fp = sum(conf[o][c] for o in CLASSES if o != c)
        fn = sum(n for p, n in conf[c].items() if p != c)
        p, r, f = prf(tp, fp, fn)
        per_class[c] = {"precision": p, "recall": r, "f1": f, "support": sum(conf[c].values())}
    n = len(truth)
    correct = sum(1 for s in per_step if s["ok"])
    non_fossil = [s for s in per_step if s["truth"] != "FOSSIL"]
    false_fossil = [s for s in non_fossil if s["pred"] == "FOSSIL"]

    tw_results, tw_hit, tw_tot, tw_extra = [], 0, 0, 0
    for sc in gt["tripwires"]:
        rec = await tripwires.evaluate(sc["event"], store=False)
        got = {a["step_id"]: a["effect"] for a in rec["alerts"]}
        hits = {s: got.get(s) == e for s, e in sc["expected"].items()}
        tw_hit += sum(hits.values())
        tw_tot += len(hits)
        extra = sorted(set(got) - set(sc["expected"]))
        tw_extra += len(extra)
        tw_results.append({"id": sc["id"], "expected": sc["expected"], "got": got, "hits": hits, "extra_alerts": extra})

    cc_results = []
    for cc in gt["change_checks"]:
        res = await changecheck.check(cc["proposal"])
        cc_results.append({"proposal": cc["proposal"], "expected": cc["expected"], "got": res["decision"],
                           "ok": res["decision"] == cc["expected"], "targets": res["parsed"]["targets"]})

    inj_docs = set(gt["injection_documents"])
    inj_cited = [s["step"] for s in per_step if set(s["cited"]) & inj_docs]
    sol02 = (vs.get("SOL-02") or {}).get("verdict")

    return {
        "provider": llm.mode(),
        "label": ("AMD-hosted models" if llm.mode() == "amd" else
                  "Offline fixture provider = rule-based heuristic baseline (no LLM). Not a model result."),
        "models": {r: llm.model_name(r) for r in ("reasoner", "vision", "embeddings")},
        "hardware": config.settings.hardware_label if llm.mode() == "amd" else "CPU (offline)",
        "evaluated_at": time.time(), "dataset": gt["dataset"], "n_steps": n,
        "accuracy": round(correct / n, 3), "per_class": per_class,
        "confusion": {t: dict(conf[t]) for t in CLASSES},
        "fence_recall": per_class["FENCE"]["recall"],
        "false_fossil_rate": round(len(false_fossil) / max(1, len(non_fossil)), 3),
        "dangerous_errors": [s["step"] for s in per_step if s["truth"] == "FENCE" and s["pred"] == "FOSSIL"],
        "citations": {"precision": round(cite_ok / cite_tot, 3) if cite_tot else None, "cited_documents": cite_tot,
                      "key_evidence_recall": round(key_hit / key_tot, 3) if key_tot else None,
                      "quotes_rejected_by_verifier": quotes_rejected,
                      "note": "precision = share of cited documents (excluding recipe context) that belong to the step's "
                              "planted story; every cited quote is verified verbatim against the source text before use."},
        "tripwires": {"recall": round(tw_hit / tw_tot, 3) if tw_tot else None, "expected_effects": tw_tot,
                      "extra_alerts": tw_extra, "scenarios": tw_results},
        "change_checks": {"accuracy": round(sum(c["ok"] for c in cc_results) / len(cc_results), 3), "cases": cc_results},
        "injection": {"documents": sorted(inj_docs), "cited_by_steps": inj_cited, "SOL-02_verdict": sol02,
                      "passed": not inj_cited and sol02 != "FOSSIL"},
        "per_step": per_step,
    }


def report(out: dict) -> None:
    pc = out["per_class"]
    print(f"provider={out['provider']}  accuracy={out['accuracy']}  FENCE recall={out['fence_recall']}  "
          f"false-FOSSIL rate={out['false_fossil_rate']}  dangerous={out['dangerous_errors']}")
    for c in CLASSES:
        print(f"  {c:8} P={pc[c]['precision']:.2f} R={pc[c]['recall']:.2f} F1={pc[c]['f1']:.2f} n={pc[c]['support']}")
    print("  confusion (truth -> predicted):", out["confusion"])
    ci = out["citations"]
    print(f"  citations: precision {ci['precision']}, key-evidence recall {ci['key_evidence_recall']}, "
          f"quotes rejected {ci['quotes_rejected_by_verifier']}")
    tw = out["tripwires"]
    print(f"  tripwires: recall {tw['recall']} of {tw['expected_effects']}, extra alerts {tw['extra_alerts']}")
    print(f"  change checks: {out['change_checks']['accuracy']}   injection passed: {out['injection']['passed']}")
    for s in out["per_step"]:
        if not s["ok"]:
            print(f"    MISS {s['step']}: truth {s['truth']} pred {s['pred']} ({s['strength']}) irrelevant={s['irrelevant_citations']}")
    for c in out["change_checks"]["cases"]:
        if not c["ok"]:
            print(f"    CC MISS {c['proposal']!r}: expected {c['expected']} got {c['got']} targets {c['targets']}")
    for t in tw["scenarios"]:
        print(f"    TW {t['id']}: hits {t['hits']} extra {t['extra_alerts']}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    try:
        out = await evaluate(args.rerun)
    finally:
        await llm.aclose()
    path = Path(args.out) if args.out else config.settings.recorded_dir / f"eval_{out['provider']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    if not args.quiet:
        report(out)
    print("written", path)


if __name__ == "__main__":
    asyncio.run(main())
