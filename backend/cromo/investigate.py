"""The investigation engine ("Why-Trail").

For one recipe step CROMO digs through the archive hop by hop:

  1. Recipe history  - current recipe line and the first archived revision that contains the step
  2. Origin          - documents explaining why the step was introduced (search + references found on the way)
  3. Dependency status - for each condition the reason relied on: does it still hold today?
  4. Counter-evidence - incidents, objections, reversals
  5. Verdict         - FOSSIL / FENCE / ACTIVE / UNKNOWN, validated: only verified quotes can be cited,
                       uncited claims are dropped, safety guards can downgrade to UNKNOWN.

The reasoning model decides what is relevant, paraphrases evidence and proposes the next
leads; a deterministic scheduler bounds the dig. Every hop is emitted as an event so the UI
can stream it.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Awaitable, Callable

from . import archive, costs, db, evidence, index, llm
from .schemas import ConcludeOut, ReadOut
from .text import DOC_REF, injection_suspect, quote_in, tokens

MAX_HOPS = 9
PER_HOP = 5
Emit = Callable[[dict], Awaitable[None]]

PRIORITY = {("open_ref", "origin"): 0, ("search", "origin"): 1, ("open_ref", "status"): 2, ("search", "status"): 3,
            ("open_ref", "counter"): 4, ("search", "counter"): 5}
HOP_LABEL = {"origin": "Origin", "status": "Dependency status", "counter": "Counter-evidence"}


def _terms(text: str) -> list[str]:
    return [t for t in tokens(text) if not t.replace(".", "").replace(",", "").isdigit() and not t.startswith("rm-")]


ITEM_RE = re.compile(r"^\s*(\d+)\.\s+")


def _recipe_items(rows: list[dict]) -> list[tuple[str, dict]]:
    """Numbered step items of a recipe document, re-joining lines that wrap."""
    items: list[tuple[str, dict]] = []
    for r in rows:
        for ln in r["text"].splitlines():
            if ITEM_RE.match(ln):
                items.append((ln.strip(), r))
            elif items and items[-1][1] is r and ln.strip() and not ln.strip().startswith(("Change note", "Prepared", "##")) \
                    and not ln.strip()[0].isupper():
                items[-1] = (items[-1][0] + " " + ln.strip(), r)
    return items


def _rterms(text: str) -> set[str]:
    return {t for t in tokens(text) if not t.startswith("rm-")}


def recipe_history(step: dict) -> dict:
    """Find the step in archived recipe documents (current + superseded revisions).

    A numbered line of an old revision is attributed to the current step it matches best (mutual best match among
    the steps of the same process), tolerating changed quantities and suppliers."""
    ix = index.get()
    proc = archive.process(step["process"])
    targets = {s["id"]: _rterms(s["instruction"]) for s in proc["steps"]}
    found = []
    revisions = []
    proc_code = step["process_code"].split()[0].lower()
    for acc, d in ix.docs.items():
        if (d.get("doc_type") or "") != "recipe":
            continue
        rows = sorted((r for r in ix.rows if r["acc"] == acc), key=lambda r: (r["page"], r["line_start"]))
        text = "\n".join(r["text"] for r in rows).lower()
        if proc_code not in text:
            continue
        revisions.append((d.get("date") or "", acc))
        best = None
        for item, row in _recipe_items(rows):
            it = _rterms(ITEM_RE.sub("", item))
            scores = {sid: (len(it & tt) / max(1, min(len(it), len(tt))), len(it & tt)) for sid, tt in targets.items()}
            sid, (o, shared) = max(scores.items(), key=lambda kv: kv[1])
            if sid != step["id"] or shared < 1 or o < 0.2 or (shared < 2 and o < 0.99):
                continue
            if best is None or o > best[0]:
                best = (o, item, row)
        if best:
            found.append({"acc": acc, "date": d.get("date"), "row": best[2], "line": best[1], "match": round(best[0], 2),
                          "title": d.get("title")})
    found.sort(key=lambda f: f["date"] or "9999")
    first = found[0] if found else None
    prev = None
    if first:
        earlier = sorted(r for r in revisions if r[0] < (first["date"] or ""))
        prev = earlier[-1][1] if earlier else None
    return {"first": first, "current": found[-1] if found else None, "all": found,
            "compare": {"a": prev, "b": first["acc"]} if prev and first else None}


class Dig:
    def __init__(self, step: dict, emit: Emit | None):
        self.step = step
        self.emit_cb = emit
        self.events: list[dict] = []
        self.evidence: dict[str, dict] = {}
        self.seen_chunks: set[str] = set()
        self.opened_refs: set[str] = set()
        self.queries_done: set[str] = set()
        self.queue: list[dict] = []
        self.hops = 0
        self.suspicious: set[str] = set()
        self.unverified = 0
        terms = list(dict.fromkeys(_terms(step["instruction"])))
        self.key_terms = sorted(terms, key=lambda t: -index.idf(t))[:5]
        self.own_codes = {step["process_code"].split()[0].lower(), step["process"].lower()}

    def useful_entity(self, ent: str) -> bool:
        e = ent.lower().strip()
        if not e or e in self.own_codes or any(e == c or e.startswith(c + " ") for c in self.own_codes):
            return False
        return not index.common(ent)

    async def emit(self, ev: dict):
        ev = {**ev, "t": round(time.time(), 3)}
        self.events.append(ev)
        if self.emit_cb:
            await self.emit_cb(ev)

    def add_evidence(self, p: dict, item, *, stance=None, claim=None, quote=None, verified=None) -> str:
        eid = f"E{len(self.evidence) + 1}"
        q = quote if quote is not None else item.quote
        ok = verified if verified is not None else quote_in(q, p["text"])
        if not ok:
            self.unverified += 1
        susp = bool(p.get("injection_flag")) or p["id"] in self.suspicious or injection_suspect(q)
        self.evidence[eid] = {
            "id": eid, "acc": p["acc"], "page": p["page"], "line_start": p["line_start"], "line_end": p["line_end"],
            "chunk": p["id"], "date": p.get("date"), "doc_type": p.get("doc_type"), "title": p.get("title"),
            "stance": stance or item.stance, "claim": claim if claim is not None else item.claim, "quote": q,
            "entities": list(getattr(item, "entities", []) or []), "verified": bool(ok), "suspicious": susp,
        }
        return eid

    def known(self) -> list[str]:
        return [f"{e['id']} ({e['date'] or 'undated'}, {e['stance']}): {e['claim']}" for e in self.evidence.values()
                if e["verified"] and not e["suspicious"]][-12:]

    def enqueue(self, kind: str, purpose: str, value: str, after: str | None = None):
        value = value.strip()
        if not value:
            return
        key = (kind, value.lower())
        if kind == "open_ref" and value.upper() in self.opened_refs:
            return
        if kind == "search" and value.lower() in self.queries_done:
            return
        if any((q["kind"], q["value"].lower()) == key for q in self.queue):
            return
        self.queue.append({"kind": kind, "purpose": purpose, "value": value, "after": after})

    def pop(self) -> dict | None:
        if not self.queue:
            return None
        self.queue.sort(key=lambda q: PRIORITY.get((q["kind"], q["purpose"]), 9))
        return self.queue.pop(0)


async def investigate(step_id: str, emit: Emit | None = None, *, store: bool = True) -> dict:
    step = archive.step(step_id)
    t0 = time.perf_counter()
    dig = Dig(step, emit)
    await dig.emit({"type": "start", "step": {k: step[k] for k in ("id", "instruction", "process", "process_name", "seq")},
                    "provider": llm.mode(), "model": llm.model_name("reasoner")})

    # ---- hop 1: recipe history (deterministic) ------------------------------
    hist = recipe_history(step)
    hop_ev = []
    first_seen = None
    if hist["current"]:
        c = hist["current"]
        p = index.passage(c["row"])
        eid = dig.add_evidence(p, None, stance="context", claim=f"Step is in the current recipe ({c['title'] or 'recipe'}).",
                               quote=c["line"], verified=True)
        hop_ev.append(eid)
    if hist["first"] and hist["first"] is not hist["current"]:
        f = hist["first"]
        p = index.passage(f["row"])
        first_seen = f["date"]
        eid = dig.add_evidence(p, None, stance="context",
                               claim=f"Earliest archived recipe revision containing the step is dated {f['date']}.",
                               quote=f["line"], verified=True)
        hop_ev.append(eid)
        # change note of the introducing revision may cite the change request
        rows = index.chunks_of(f["acc"])
        full = "\n".join(r["text"] for r in rows)
        note = full.split("Change note", 1)[1][:400] if "Change note" in full else ""
        for ref in DOC_REF.findall(note):
            dig.enqueue("open_ref", "origin", ref)
    elif hist["first"]:
        first_seen = hist["first"]["date"]
    dig.hops += 1
    await dig.emit({"type": "hop", "n": dig.hops, "kind": "recipe", "label": "Recipe history",
                    "detail": (f"Found in {len(hist['all'])} archived recipe revision(s); first seen {first_seen or 'unknown'}."
                               if hist["all"] else "Step text not found in archived recipes."),
                    "evidence": [dig.evidence[e] for e in hop_ev], "query": None, "compare": hist.get("compare")})

    seen_recipe_accs = {f["acc"] for f in hist["all"]}
    dig.enqueue("search", "origin", step["instruction"])

    # ---- hops 2..n ----------------------------------------------------------
    while dig.hops < MAX_HOPS:
        item = dig.pop()
        if item is None:
            break
        purpose = item["purpose"]
        if item["kind"] == "open_ref":
            ref = item["value"].upper()
            dig.opened_refs.add(ref)
            accs = [a for a in index.by_ref(ref) if a not in seen_recipe_accs]
            passages = [p for a in accs for p in index.chunks_of(a) if p["id"] not in dig.seen_chunks][:PER_HOP]
            label = f"Follow reference {ref}"
        else:
            dig.queries_done.add(item["value"].lower())
            passages = await index.search(item["value"], k=PER_HOP, exclude=dig.seen_chunks,
                                          exclude_types={"recipe"}, after=item.get("after"))
            label = f"Search: “{item['value'][:70]}”"
        if not passages:
            continue
        for p in passages:
            dig.seen_chunks.add(p["id"])
        dig.hops += 1
        await dig.emit({"type": "hop_started", "n": dig.hops, "kind": purpose, "label": HOP_LABEL[purpose],
                        "query": label, "documents": sorted({p["acc"] for p in passages})})
        focus = sorted({ent for e in dig.evidence.values() if e["stance"] == "reason" for ent in e["entities"]
                        if dig.useful_entity(ent)})[:8]
        payload = {"step_id": step["id"], "step_text": step["instruction"], "process": step["process_name"],
                   "purpose": purpose, "known": dig.known(), "focus": focus, "key_terms": dig.key_terms,
                   "passages": [{k: p[k] for k in ("id", "acc", "date", "doc_type", "title", "text")} for p in passages]}
        try:
            read = await llm.run_task("investigate.read", payload, ReadOut)
        except llm.ProviderError as e:
            await dig.emit({"type": "warning", "message": f"Reading failed for this hop: {e}"})
            continue
        dig.suspicious |= set(read.suspicious_passages)
        by_id = {p["id"]: p for p in passages}
        new = []
        for it in read.evidence:
            p = by_id.get(it.passage_id)
            if not p or not it.relevant or not it.quote:
                continue
            eid = dig.add_evidence(p, it)
            new.append(eid)
        ignored = sorted({p["acc"] for p in passages if p.get("injection_flag") or p["id"] in dig.suspicious})
        await dig.emit({"type": "hop", "n": dig.hops, "kind": purpose, "label": HOP_LABEL[purpose], "query": label,
                        "evidence": [dig.evidence[e] for e in new], "ignored_injection": ignored,
                        "documents": sorted({p["acc"] for p in passages})})
        # schedule follow-ups proposed by the model + deterministic status checks
        for ref in read.follow_up.open_refs[:4]:
            if DOC_REF.fullmatch(ref.strip().upper() or ""):
                dig.enqueue("open_ref", "origin" if purpose == "origin" else purpose, ref)
        for q in read.follow_up.queries[:3]:
            dig.enqueue("search", q.purpose, q.query)
        for e in new:
            ev = dig.evidence[e]
            if ev["stance"] == "reason" and ev["verified"] and not ev["suspicious"]:
                for ent in [x for x in ev["entities"] if dig.useful_entity(x)][:3]:
                    dig.enqueue("search", "status", ent, after=ev["date"])
        if new and not any(q["purpose"] == "counter" for q in dig.queue) and \
                not any(k.endswith(" incident near-miss complaint") for k in dig.queries_done):
            key = " ".join(_terms(step["instruction"])[:4])
            dig.enqueue("search", "counter", f"{key} incident near-miss complaint")

    # ---- verdict -------------------------------------------------------------
    usable = [e for e in dig.evidence.values() if e["verified"] and not e["suspicious"]]
    await dig.emit({"type": "concluding", "evidence_count": len(usable)})
    payload = {"step_id": step["id"], "step_text": step["instruction"], "process": step["process_name"],
               "first_seen": first_seen,
               "evidence": [{k: e[k] for k in ("id", "acc", "date", "doc_type", "stance", "claim", "quote", "entities")}
                            for e in usable]}
    try:
        out = await llm.run_task("investigate.conclude", payload, ConcludeOut)
    except llm.ProviderError as e:
        out = ConcludeOut(verdict="UNKNOWN", reason=f"Model failed to conclude: {e}")
    v, notes, removed = evidence.validate(out, dig.evidence)
    if dig.unverified:
        notes.append(f"{dig.unverified} quote(s) could not be matched to the source text and were not used.")
    ignored = sorted({e["acc"] for e in dig.evidence.values() if e["suspicious"]})
    if ignored:
        notes.append("Instruction-like text found in " + ", ".join(ignored) + ": treated as data and excluded from the verdict.")
    st = evidence.strength(v, dig.evidence)
    cited = set(st["cited"]) | {e for e in dig.evidence if dig.evidence[e]["stance"] == "context"}
    verdict = {
        "step_id": step["id"], "process": step["process"], "process_name": step["process_name"],
        "instruction": step["instruction"], **v, "first_seen": first_seen, "strength": st, "guards": notes,
        "evidence": {k: e for k, e in dig.evidence.items() if k in cited or e["suspicious"]},
        "cost": costs.step_cost(step), "provider": llm.mode(), "model": llm.model_name("reasoner"),
        "hops": dig.hops, "duration_s": round(time.perf_counter() - t0, 2), "created_at": time.time(),
        "ignored_injection_docs": ignored,
        "stats": {"evidence_total": len(dig.evidence), "unverified_quotes": dig.unverified,
                  "suspicious": sum(1 for e in dig.evidence.values() if e["suspicious"]), "uncited_removed": removed},
    }
    await dig.emit({"type": "verdict", "verdict": verdict})
    if store:
        db.ex("INSERT OR REPLACE INTO investigations(step_id, verdict_json, events_json, provider, model, created_at, duration_s) "
              "VALUES(?,?,?,?,?,?,?)", (step["id"], json.dumps(verdict, ensure_ascii=False),
                                        json.dumps(dig.events, ensure_ascii=False), llm.mode(), llm.model_name("reasoner"),
                                        time.time(), verdict["duration_s"]))
    return verdict


async def investigate_all(step_ids: list[str] | None = None, *, concurrency: int = 4, progress=None) -> list[dict]:
    ids = step_ids or [s["id"] for s in archive.steps()]
    sem = asyncio.Semaphore(concurrency)
    out = []

    async def one(sid):
        async with sem:
            v = await investigate(sid)
            out.append(v)
            if progress:
                progress(len(out), len(ids), sid, v["verdict"])

    await asyncio.gather(*(one(s) for s in ids))
    return out


def stored(step_id: str) -> dict | None:
    r = db.q1("SELECT verdict_json FROM investigations WHERE step_id=?", (step_id,))
    return json.loads(r["verdict_json"]) if r else None


def stored_events(step_id: str) -> list[dict]:
    r = db.q1("SELECT events_json FROM investigations WHERE step_id=?", (step_id,))
    return json.loads(r["events_json"]) if r else []


def all_stored() -> dict[str, dict]:
    return {r["step_id"]: json.loads(r["verdict_json"]) for r in db.q("SELECT step_id, verdict_json FROM investigations")}
