"""Retrieval check: does document expansion (the reasoner's bilingual keywords) help search find the right documents?

  python eval/retrieval_eval.py

For every step of the planted ground truth, the step's instruction is used as the search query (CROMO's first
"origin" search does exactly this) and we measure how many of the step's key documents appear in the top 5 / top 10
results, and the reciprocal rank of the first one. Run it after an ingest whose metadata came from a model (AMD
route): it compares lexical retrieval with and without the keywords. No model is called: the query vectors are the
local hashed n-grams. Works on a temporary copy of the database. Writes data/recorded/retrieval_eval.json.

This is an evaluation script: it reads eval/ground_truth.json, which the product never does.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DB = ROOT / "data" / "runtime" / "cromo.db"


def main() -> None:
    if not SRC_DB.exists():
        sys.exit("No ingested database (data/runtime/cromo.db). Ingest first.")
    tmp = Path(tempfile.mkdtemp(prefix="cromo-retrieval-"))
    (tmp / "runtime").mkdir()
    shutil.copy(SRC_DB, tmp / "runtime" / "cromo.db")
    os.environ["CROMO_DATA_DIR"] = str(tmp)
    os.environ["CROMO_EMBEDDINGS_MODEL"] = ""  # query vectors: local hashed n-grams, no model call
    sys.path.insert(0, str(ROOT / "backend"))
    from cromo import archive, config, db, index, ingest

    config.reload_settings()
    truth = json.loads((ROOT / "eval" / "ground_truth.json").read_text(encoding="utf-8"))["steps"]
    meta_sources = {r["meta_source"] for r in db.q("SELECT DISTINCT meta_source FROM documents")}

    async def run(mode: str) -> dict:
        os.environ["CROMO_DOC_EXPANSION"] = mode
        db.ex("UPDATE chunks SET vector=NULL")
        await ingest.embed_all()
        index.invalidate()
        rows = []
        for sid, t in truth.items():
            key = set(t.get("key_accessions") or [])
            if not key:
                continue
            hits = await index.search(archive.step(sid)["instruction"], k=20)
            docs = list(dict.fromkeys(h["acc"] for h in hits))
            rank = next((i + 1 for i, a in enumerate(docs) if a in key), None)
            rows.append({"step": sid, "label": t["label"], "key": len(key),
                         "r5": len(key & set(docs[:5])) / len(key), "r10": len(key & set(docs[:10])) / len(key),
                         "rr": 1 / rank if rank else 0.0})
        return {"steps": len(rows), "recall_at_5": round(statistics.mean(r["r5"] for r in rows), 3),
                "recall_at_10": round(statistics.mean(r["r10"] for r in rows), 3),
                "mrr": round(statistics.mean(r["rr"] for r in rows), 3), "per_step": rows}

    async def go():
        return {"off": await run("off"), "on": await run("on")}

    res = asyncio.run(go())
    out = {"what": "search with the step instruction; key documents of the planted ground truth in the results",
           "metadata_source": sorted(m for m in meta_sources if m),
           "without_expansion": {k: v for k, v in res["off"].items() if k != "per_step"},
           "with_expansion": {k: v for k, v in res["on"].items() if k != "per_step"},
           "note": "Lexical hybrid retrieval (BM25 + local hashed n-gram cosine). 'with_expansion' adds the reasoner's "
                   "bilingual keywords and summary as search-only terms. Measured on the current ingest."}
    dest = ROOT / "data" / "recorded" / "retrieval_eval.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k in ("without_expansion", "with_expansion"):
        print(f"{k:18s} {out[k]}")
    print("metadata source:", out["metadata_source"], "| written", dest)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
