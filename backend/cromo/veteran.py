"""Veteran interview mode: capture knowledge before it retires.

For a step CROMO could not explain (UNKNOWN, or only weakly evidenced) it drafts targeted questions for
experienced staff. Their answer - typed, or a voice recording transcribed by the SPEECH model on AMD - is
stored as a dated "interview record" document (accession INT-NNNN), ingested like any archive document
(untrusted text, verified quotes) and the step is re-investigated. Testimony is an informal source: on its
own it can never make the evidence 'Strong'.
"""

from __future__ import annotations

import datetime as dt
import json
import re

from . import archive, db, ingest, investigate, llm
from .schemas import VeteranQuestionsOut

INT_RE = re.compile(r"^INT-\d{4}$")
PEOPLE_RE = re.compile(r"\b([A-Z]\.\s?[A-Z][a-z]{2,}|Ing\. [A-Z][a-z]+|Dr\.ssa [A-Z][a-z]+)\b")


def _people(v: dict) -> list[str]:
    names: list[str] = []
    for e in (v or {}).get("evidence", {}).values():
        for m in PEOPLE_RE.findall(e.get("quote", "") + " " + e.get("claim", "")):
            if m not in names:
                names.append(m)
    return names[:5]


async def questions(step_id: str) -> dict:
    st = archive.step(step_id)
    v = investigate.stored(step_id) or {}
    payload = {"step_id": step_id, "step_text": st["instruction"], "process": st["process_name"],
               "verdict": v.get("verdict"), "reason": v.get("reason", ""), "open_questions": v.get("open_questions", []),
               "first_seen": v.get("first_seen"), "people": _people(v),
               "known": [e.get("claim", "") for e in (v.get("evidence") or {}).values() if e.get("claim")][:8]}
    out = await llm.run_task("veteran.questions", payload, VeteranQuestionsOut)
    return {"step_id": step_id, "questions": out.questions[:6], "who": out.who_to_ask or payload["people"],
            "provider": llm.mode()}


def _next_acc() -> str:
    r = db.q1("SELECT acc FROM documents WHERE acc LIKE 'INT-%' ORDER BY acc DESC LIMIT 1")
    n = int(r["acc"][4:]) + 1 if r else 1
    return f"INT-{n:04d}"


def _clean(s: str, n: int) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s or "")
    return s.strip()[:n]


async def record(step_id: str, name: str, role: str, answer: str, *, source: str = "typed") -> dict:
    st = archive.step(step_id)
    acc = _next_acc()
    today = dt.date.today().isoformat()
    name, role, answer = _clean(name, 80), _clean(role, 120), _clean(answer, 6000)
    lines = [
        "INTERVIEW RECORD",
        f"Ref. {acc}    Date: {today}",
        f"Interviewee: {name} ({role})",
        f"Subject: why step {st['id']} of {st['process_code']} exists - \"{st['instruction']}\"",
        f"Answer ({'transcribed from a voice recording' if source == 'voice' else 'typed'}):",
    ] + [ln for ln in re.split(r"(?<=[.!?])\s+", answer) if ln.strip()] + [
        "Note: testimony recorded by CROMO; it reflects one person's recollection.",
    ]
    page = {"page": 1, "width": 0, "height": 0, "lines": [{"text": ln} for ln in lines], "source": "testimony", "model": None}
    text = "\n".join(lines)
    meta = await ingest._metadata(acc, text)
    m = meta[0]
    chunks = ingest._chunk_lines(acc, [page])
    with db.tx() as c:
        c.execute("INSERT INTO documents(acc,pages,has_text_layer,text,title,doc_type,date,lang,refs_json,entities_json,summary,"
                  "meta_source,text_source,injection_flag,ingested_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now'))",
                  (acc, 1, 1, text, f"Interview record - {name}", "interview record", today, m.language,
                   json.dumps({"own": [acc], "cited": m.referenced_documents}),
                   json.dumps({"organizations": m.organizations, "materials": m.materials, "equipment": m.equipment,
                               "products": m.products, "regulations": m.regulations, "people": [name]}),
                   f"Testimony of {name} about {st['id']}", meta[1], source, int(m.suspicious_instructions)))
        c.execute("INSERT INTO pages(acc,page,width,height,lines_json,source,model) VALUES(?,?,?,?,?,?,?)",
                  (acc, 1, 0, 0, json.dumps(page["lines"], ensure_ascii=False), "testimony", None))
        for ch in chunks:
            c.execute("INSERT INTO chunks(id,acc,page,line_start,line_end,text) VALUES(?,?,?,?,?,?)",
                      (ch["id"], acc, ch["page"], ch["line_start"], ch["line_end"], ch["text"]))
    await ingest.embed_all()
    from . import index

    index.invalidate()
    return {"acc": acc, "date": today, "step_id": step_id}


def purge() -> int:
    """Remove all interview records (used before benchmark/evaluation runs so testimony cannot leak into scores)."""
    n = db.q1("SELECT COUNT(*) n FROM documents WHERE acc LIKE 'INT-%'")["n"]
    with db.tx() as c:
        c.execute("DELETE FROM chunks WHERE acc LIKE 'INT-%'")
        c.execute("DELETE FROM pages WHERE acc LIKE 'INT-%'")
        c.execute("DELETE FROM documents WHERE acc LIKE 'INT-%'")
    from . import index

    index.invalidate()
    return n
