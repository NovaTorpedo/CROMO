"""Pre-compute and cache Evolus results used by the demo (spends platform credits once; results are cached).

  python scripts/evolus_precompute.py compare            # AI Tool 'compare' for every recipe revision pair investigations show
  python scripts/evolus_precompute.py extract [--limit N] # document extractor on archive documents (needs extractor ids)
  python scripts/evolus_precompute.py library [--limit N] # upload transcriptions to the knowledge library (needs library id)
  add --dry-run to only print what would be called

Prints credits consumed. Respects the 60 requests/minute workspace limit.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from cromo import archive, db, evolus, investigate  # noqa: E402


def compare_pairs() -> list[tuple[str, str]]:
    pairs = set()
    for sid in [s["id"] for s in archive.steps()]:
        for ev in investigate.stored_events(sid):
            c = ev.get("compare")
            if c and c.get("a") and c.get("b"):
                pairs.add((c["a"], c["b"]))
    return sorted(pairs)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["compare", "extract", "library"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    before = db.q1("SELECT COALESCE(SUM(credits),0) c FROM evolus_calls")["c"]
    if a.what == "compare":
        items = compare_pairs()
        print(f"{len(items)} revision pairs")
        for x, y in items[: a.limit or None]:
            cached = await evolus.compare_docs(x, y, cached_only=True)
            print(f"  {x} -> {y}: {'cached' if cached else 'calling Evolus'}")
            if not cached and not a.dry_run:
                r = await evolus.compare_docs(x, y)
                print(f"     credits {r.get('creditsConsumed')}")
    else:
        accs = archive.list_accessions()[: a.limit or None]
        for acc in accs:
            if a.dry_run:
                print("  would process", acc)
                continue
            try:
                r = await (evolus.extract(acc) if a.what == "extract" else evolus.library_upload(acc))
                print(f"  {acc}: ok {r.get('credits') or ''}")
            except evolus.EvolusError as e:
                print(f"  {acc}: FAILED {e}")
                if e.status in (401, 402, 403):
                    break
    after = db.q1("SELECT COALESCE(SUM(credits),0) c FROM evolus_calls")["c"]
    print(f"credits consumed in this run: {after - before:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
