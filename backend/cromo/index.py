"""Hybrid retrieval over archive chunks: BM25 (lexical) + embedding cosine (semantic)."""

from __future__ import annotations

import json
import math
import os
import threading
from collections import Counter
from dataclasses import dataclass

import numpy as np

from . import db, llm
from .text import tokens


@dataclass
class _Index:
    ids: list[str]
    rows: list[dict]
    toks: list[Counter]
    lens: np.ndarray
    df: Counter
    vecs: np.ndarray | None
    docs: dict[str, dict]


_idx: _Index | None = None
_lock = threading.Lock()


def invalidate() -> None:
    global _idx
    with _lock:
        _idx = None


def expansion_enabled(meta_source: str | None) -> bool:
    """Document expansion is on for metadata written by a model (AMD reasoner or Evolus extractor), never for the
    offline fixture heuristic, so the rule-based baseline stays a pure lexical baseline. CROMO_DOC_EXPANSION=on|off
    overrides it (the retrieval evaluation uses this to measure the effect)."""
    mode = os.environ.get("CROMO_DOC_EXPANSION", "auto").strip().lower()
    if mode in ("on", "off"):
        return mode == "on"
    return (meta_source or "") not in ("", "fixture")


def _expansion_terms(d: dict) -> Counter:
    """Search-only terms for every chunk of a document: the model's bilingual keywords and English summary.

    They change which chunks a search finds, never the passage text shown to the model or cited, so quote
    verification is unaffected."""
    ent = d.get("entities") or {}
    text = " ".join([*(ent.get("keywords") or []), d.get("summary") or ""])
    return Counter(set(tokens(text)))  # each term once: expansion nudges ranking, it doesn't dominate it


def _build() -> _Index:
    docs = {}
    for r in db.q("SELECT acc, title, doc_type, date, refs_json, entities_json, injection_flag, pages, text_source, summary, "
                  "meta_source FROM documents"):
        d = dict(r)
        d["refs"] = json.loads(d.pop("refs_json") or "{}")
        d["entities"] = json.loads(d.pop("entities_json") or "{}")
        docs[d["acc"]] = d
    rows = [dict(r) for r in db.q("SELECT id, acc, page, line_start, line_end, text, vector FROM chunks ORDER BY id")]
    expand = {acc: _expansion_terms(d) for acc, d in docs.items() if expansion_enabled(d.get("meta_source"))}
    toks = [Counter(tokens(r["text"])) + expand.get(r["acc"], Counter()) for r in rows]
    df = Counter()
    for t in toks:
        df.update(t.keys())
    vecs = None
    if rows and all(r["vector"] for r in rows):
        vecs = np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
    for r in rows:
        r.pop("vector", None)
    return _Index([r["id"] for r in rows], rows, toks, np.array([sum(t.values()) for t in toks] or [0], dtype=float), df,
                  vecs, docs)


def get() -> _Index:
    global _idx
    with _lock:
        if _idx is None:
            _idx = _build()
        return _idx


def idf(term: str) -> float:
    ix = get()
    n = max(1, len(ix.rows))
    return math.log(1 + n / (1 + ix.df.get(term, 0)))


def common(phrase: str, share: float = 0.06) -> bool:
    """True when a phrase is too common in the archive to be a useful search on its own."""
    ix = get()
    toks = tokens(phrase)
    if not toks:
        return True
    n = max(1, len(ix.rows))
    return all(ix.df.get(t, 0) / n > share for t in toks)


def doc_meta(acc: str) -> dict:
    return get().docs.get(acc, {})


def passage(row: dict) -> dict:
    d = get().docs.get(row["acc"], {})
    return {"id": row["id"], "acc": row["acc"], "page": row["page"], "line_start": row["line_start"],
            "line_end": row["line_end"], "text": row["text"], "date": d.get("date"), "doc_type": d.get("doc_type"),
            "title": d.get("title"), "injection_flag": bool(d.get("injection_flag"))}


def _bm25(ix: _Index, q: list[str], k1=1.4, b=0.75) -> np.ndarray:
    n = len(ix.rows)
    avg = float(ix.lens.mean()) if n else 1.0
    scores = np.zeros(n)
    for t in set(q):
        df = ix.df.get(t, 0)
        if not df:
            continue
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for i, tc in enumerate(ix.toks):
            f = tc.get(t, 0)
            if f:
                scores[i] += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * ix.lens[i] / avg))
    return scores


async def search(query: str, *, k: int = 6, exclude: set[str] | None = None, after: str | None = None,
                 before: str | None = None, doc_types: set[str] | None = None, exclude_types: set[str] | None = None,
                 accs: set[str] | None = None) -> list[dict]:
    ix = get()
    if not ix.rows:
        return []
    q = tokens(query)
    lex = _bm25(ix, q)
    if lex.max() > 0:
        lex = lex / lex.max()
    sem = np.zeros(len(ix.rows))
    if ix.vecs is not None:
        qv = (await llm.embed([query], stage="embed.query"))[0]
        if qv.shape[0] == ix.vecs.shape[1]:
            sem = ix.vecs @ qv
            sem = np.clip(sem, 0, None)
            if sem.max() > 0:
                sem = sem / sem.max()
    score = 0.55 * lex + 0.45 * sem
    order = np.argsort(-score)
    out, per_doc = [], Counter()
    for i in order:
        if score[i] <= 0.05:
            break
        r = ix.rows[i]
        if exclude and r["id"] in exclude:
            continue
        d = ix.docs.get(r["acc"], {})
        date = d.get("date") or ""
        if accs is not None and r["acc"] not in accs:
            continue
        if after and date and date <= after:
            continue
        if before and date and date >= before:
            continue
        if doc_types and (d.get("doc_type") or "") not in doc_types:
            continue
        if exclude_types and (d.get("doc_type") or "") in exclude_types:
            continue
        if per_doc[r["acc"]] >= 2:
            continue
        per_doc[r["acc"]] += 1
        p = passage(r)
        p["score"] = round(float(score[i]), 3)
        out.append(p)
        if len(out) >= k:
            break
    return out


def by_ref(ref: str) -> list[str]:
    """Accession numbers of documents whose own reference number is `ref`."""
    ix = get()
    ref = ref.upper()
    hits = [acc for acc, d in ix.docs.items() if ref in [x.upper() for x in (d.get("refs") or {}).get("own", [])]]
    if hits:
        return hits
    # fall back to documents that show the number near the top (title / "Ref." line)
    return [r["acc"] for r in ix.rows if r["line_start"] == 0 and ref in r["text"][:220].upper()][:2]


def chunks_of(acc: str) -> list[dict]:
    return [passage(r) for r in get().rows if r["acc"] == acc]
