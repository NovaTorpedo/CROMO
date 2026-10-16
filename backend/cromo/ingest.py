"""Archive ingestion: page text (text layer or VISION model) -> metadata -> chunks -> embeddings."""

from __future__ import annotations

import asyncio
import json
import time

import numpy as np

from . import archive, config, db, llm
from .schemas import MetadataOut
from .text import injection_suspect, tokens

CHUNK_WORDS = 80


def _chunk_lines(acc: str, pages: list[dict]) -> list[dict]:
    chunks = []
    for pg in pages:
        lines = [ln["text"] for ln in pg["lines"]]
        cur, start, words = [], 0, 0
        for i, ln in enumerate(lines):
            if not cur:
                start = i
            cur.append(ln)
            words += len(ln.split())
            if words >= CHUNK_WORDS:
                chunks.append({"acc": acc, "page": pg["page"], "line_start": start, "line_end": i, "text": "\n".join(cur)})
                # one line of overlap keeps sentences that straddle chunks findable
                cur, words = [ln], len(ln.split())
                start = i
        if cur and (not chunks or chunks[-1]["line_end"] != len(lines) - 1 or chunks[-1]["page"] != pg["page"]):
            chunks.append({"acc": acc, "page": pg["page"], "line_start": start, "line_end": len(lines) - 1, "text": "\n".join(cur)})
    for n, c in enumerate(chunks):
        c["id"] = f"{acc}#{n}"
    return chunks


async def _metadata(acc: str, text: str) -> tuple[MetadataOut, str]:
    src = config.settings.metadata_source
    if src in ("auto", "evolus"):
        from . import evolus

        cached = evolus.cached_extraction(acc)
        if cached is not None:
            return MetadataOut.model_validate(evolus.normalise_extraction(cached)), "evolus-extractor"
    out = await llm.run_task("extract.metadata", {"acc": acc, "text": text}, MetadataOut)
    return out, ("reasoner" if config.settings.is_live else "fixture")


async def ingest_doc(acc: str) -> dict:
    t0 = time.perf_counter()
    layer = archive.text_layer(acc)
    pages = []
    if layer:
        for pg in layer["pages"]:
            pages.append({"page": pg["page"], "width": pg["width"], "height": pg["height"], "lines": pg["lines"],
                          "source": "text_layer", "model": None})
        text_source = "text_layer"
    else:
        for k in range(1, archive.page_count(acc) + 1):
            data = archive.page_path(acc, k).read_bytes()
            tr = await llm.transcribe(data)
            pages.append({"page": k, "width": 1000, "height": 1414, "lines": tr["lines"], "source": tr["source"],
                          "model": tr.get("model")})
        text_source = pages[0]["source"] if pages else "none"
    t_text = time.perf_counter() - t0
    text = "\n".join(ln["text"] for pg in pages for ln in pg["lines"])
    meta, meta_source = await _metadata(acc, text)
    t_meta = time.perf_counter() - t0 - t_text
    chunks = _chunk_lines(acc, pages)
    inj = injection_suspect(text) or meta.suspicious_instructions
    with db.tx() as c:
        c.execute("DELETE FROM chunks WHERE acc=?", (acc,))
        c.execute("DELETE FROM pages WHERE acc=?", (acc,))
        c.execute(
            "INSERT OR REPLACE INTO documents(acc,pages,has_text_layer,text,title,doc_type,date,lang,refs_json,entities_json,"
            "summary,meta_source,text_source,injection_flag,ingested_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (acc, len(pages), int(bool(layer)), text, meta.title, meta.doc_type, meta.date, meta.language,
             json.dumps({"own": meta.reference_numbers, "cited": meta.referenced_documents}),
             json.dumps({"organizations": meta.organizations, "materials": meta.materials, "equipment": meta.equipment,
                         "products": meta.products, "regulations": meta.regulations, "people": meta.people,
                         "keywords": meta.keywords}),
             meta.summary, meta_source, text_source, int(inj), time.time()))
        for pg in pages:
            c.execute("INSERT INTO pages(acc,page,width,height,lines_json,source,model) VALUES(?,?,?,?,?,?,?)",
                      (acc, pg["page"], pg["width"], pg["height"], json.dumps(pg["lines"], ensure_ascii=False),
                       pg["source"], pg["model"]))
        for ch in chunks:
            c.execute("INSERT INTO chunks(id,acc,page,line_start,line_end,text) VALUES(?,?,?,?,?,?)",
                      (ch["id"], acc, ch["page"], ch["line_start"], ch["line_end"], ch["text"]))
    return {"acc": acc, "pages": len(pages), "scanned": not layer, "t_text": t_text, "t_meta": t_meta,
            "chunks": len(chunks)}


async def embed_all() -> float:
    """Embed every chunk that has no vector yet (new or re-ingested documents)."""
    from .index import expansion_enabled

    rows = db.q("SELECT c.id, c.text, d.title, d.doc_type, d.date, d.entities_json, d.meta_source FROM chunks c "
                "JOIN documents d ON d.acc=c.acc WHERE c.vector IS NULL ORDER BY c.id")
    t0 = time.perf_counter()

    def keywords(r) -> str:
        if not expansion_enabled(r["meta_source"]):
            return ""
        return " ".join(json.loads(r["entities_json"] or "{}").get("keywords") or [])

    texts = [f"{r['doc_type'] or ''} {r['date'] or ''} {r['title'] or ''} {keywords(r)}\n{r['text']}" for r in rows]
    vecs = await llm.embed(texts, stage="embed.chunks") if texts else np.zeros((0, 1))
    with db.tx() as c:
        for r, v in zip(rows, vecs):
            c.execute("UPDATE chunks SET vector=? WHERE id=?", (np.asarray(v, dtype=np.float32).tobytes(), r["id"]))
    return time.perf_counter() - t0


async def ingest_all(*, force: bool = False, limit: int | None = None, progress=None,
                     accs: list[str] | None = None, tolerate_failures: bool = False) -> dict:
    """Ingest documents. With tolerate_failures, a document whose model call keeps failing is skipped and listed in
    stats["failed"] (a resumable run retries it later); otherwise the first failure is raised after the batch."""
    accs = archive.list_accessions() if accs is None else accs
    if limit:
        accs = accs[:limit]
    done = {r["acc"] for r in db.q("SELECT acc FROM documents")} if not force else set()
    todo = [a for a in accs if a not in done]
    sem = asyncio.Semaphore(config.settings.max_concurrency)
    results: list[dict] = []
    failed: dict[str, Exception] = {}
    t0 = time.perf_counter()

    async def one(acc):
        async with sem:
            try:
                r = await ingest_doc(acc)
            except llm.ProviderError as e:
                failed[acc] = e
                return
            results.append(r)
            if progress:
                progress(len(results), len(todo), acc)

    await asyncio.gather(*(one(a) for a in todo))
    if failed and not tolerate_failures:
        raise next(iter(failed.values()))
    t_ingest = time.perf_counter() - t0
    t_embed = await embed_all()  # only chunks without a vector (also after a resumed ingest)
    from . import index

    index.invalidate()
    pages = sum(r["pages"] for r in results)
    scanned = sum(r["pages"] for r in results if r["scanned"])
    total = t_ingest + t_embed
    stats = {
        "documents": len(results), "pages": pages, "scanned_pages": scanned, "seconds": round(total, 2),
        "pages_per_min": round(pages / total * 60, 1) if total > 0 else None,
        "scanned_pages_per_min": round(scanned / max(1e-6, sum(r["t_text"] for r in results if r["scanned"])) * 60 *
                                       config.settings.max_concurrency, 1) if scanned else None,
        "embed_seconds": round(t_embed, 2), "provider": llm.mode(), "finished_at": time.time(), "failed": sorted(failed),
        "models": {"vision": llm.model_name("vision"), "reasoner": llm.model_name("reasoner"),
                   "embeddings": llm.model_name("embeddings")},
    }
    if todo:
        db.kv_set("ingest_stats", stats)
    return stats


def doc_tokens(acc: str) -> list[str]:
    r = db.q1("SELECT text FROM documents WHERE acc=?", (acc,))
    return tokens(r["text"]) if r else []
