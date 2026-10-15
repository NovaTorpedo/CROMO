"""Command line: python -m cromo.cli <command>

  ingest [--force] [--limit N]     ingest the archive (vision / metadata / embeddings)
  investigate [STEP ...|--all]     run investigations and store verdicts
  bootstrap                        ingest + investigate everything if the database is empty
  status                           print a summary of stored verdicts
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter

from . import config, db, ingest, investigate, llm


def _p(*a):
    print(*a, flush=True)


async def _bootstrap(force: bool = False):
    have_docs = db.q1("SELECT COUNT(*) n FROM documents")["n"]
    if force or not have_docs:
        _p(f"[cromo] ingesting archive ({llm.mode()} mode)...")
        st = await ingest.ingest_all(force=force)
        _p(f"[cromo] ingested {st['documents']} documents / {st['pages']} pages in {st['seconds']} s")
    have_inv = db.q1("SELECT COUNT(*) n FROM investigations")["n"]
    if force or not have_inv:
        _p("[cromo] investigating all steps...")
        vs = await investigate.investigate_all(concurrency=config.settings.max_concurrency)
        _p("[cromo] verdicts:", dict(Counter(v["verdict"] for v in vs)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cromo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ingest")
    a.add_argument("--force", action="store_true")
    a.add_argument("--limit", type=int)
    b = sub.add_parser("investigate")
    b.add_argument("steps", nargs="*")
    b.add_argument("--all", action="store_true")
    c = sub.add_parser("bootstrap")
    c.add_argument("--force", action="store_true")
    sub.add_parser("status")
    args = ap.parse_args(argv)

    async def run():
        try:
            if args.cmd == "ingest":
                st = await ingest.ingest_all(force=args.force, limit=args.limit,
                                             progress=lambda i, n, acc: _p(f"  {i}/{n} {acc}") if i % 20 == 0 or i == n else None)
                _p(st)
            elif args.cmd == "investigate":
                ids = None if args.all or not args.steps else args.steps
                vs = await investigate.investigate_all(ids, concurrency=config.settings.max_concurrency,
                                                       progress=lambda i, n, s, v: _p(f"  {i}/{n} {s}: {v}"))
                _p(dict(Counter(v["verdict"] for v in vs)))
            elif args.cmd == "bootstrap":
                await _bootstrap(args.force)
            elif args.cmd == "status":
                vs = investigate.all_stored()
                _p(dict(Counter(v["verdict"] for v in vs.values())))
                for sid in sorted(vs):
                    v = vs[sid]
                    _p(f"  {sid:7} {v['verdict']:8} {v['strength']['grade']:12} {v['provider']}")
        finally:
            await llm.aclose()

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
