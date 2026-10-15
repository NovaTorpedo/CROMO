"""OFFLINE FIXTURE PROVIDER - deterministic stand-in for the AMD-hosted models.

Used when no AMD endpoint is configured, so the whole product runs end to end
offline. It is clearly labelled in the UI and its evaluation numbers are
reported as a *rule-based heuristic baseline*, never as model results.

  * vision      -> recorded transcriptions keyed by the page image's SHA-256
                   (fixtures/vision/, written by the archive generator)
  * embeddings  -> feature-hashing vectors (no model)
  * reasoning   -> keyword / cue-word heuristics per task

It never reads eval/ground_truth.json or the generator (tests enforce this).
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache

import numpy as np

from . import config
from .text import DOC_REF, STEP_ID, best_sentence, fold, injection_suspect, norm, sentences, tokens

# ----------------------------------------------------------------------------
# vision
# ----------------------------------------------------------------------------


def transcribe(image_bytes: bytes) -> dict:
    sha = hashlib.sha256(image_bytes).hexdigest()
    p = config.settings.fixtures_dir / "vision" / f"{sha}.json"
    if not p.is_file():
        return {"lines": [], "source": "fixture-missing", "model": "fixture-vision"}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"lines": data["lines"], "source": "fixture-recorded", "model": "fixture-vision (recorded transcription)"}


# ----------------------------------------------------------------------------
# embeddings (feature hashing)
# ----------------------------------------------------------------------------
DIM = 384


def _h(t: str) -> tuple[int, float]:
    d = hashlib.md5(t.encode()).digest()
    return int.from_bytes(d[:4], "little") % DIM, (1.0 if d[4] & 1 else -1.0)


def embed(texts: list[str]) -> np.ndarray:
    out = np.zeros((len(texts), DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        toks = tokens(t)
        feats = toks + [a + "_" + b for a, b in zip(toks, toks[1:])]
        for f in feats:
            j, s = _h(f)
            out[i, j] += s
    out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
    return out


# ----------------------------------------------------------------------------
# lexicons
# ----------------------------------------------------------------------------
DOC_TYPES = [
    ("deviation report", ["deviation report"]), ("incident report", ["incident report"]),
    ("near-miss report", ["near-miss report"]), ("change request", ["change request"]),
    ("lab test report", ["laboratory test report", "laboratory report"]),
    ("supplier qualification", ["supplier qualification"]),
    ("equipment record", ["commissioning record", "equipment record", "equipment modification", "purchase record"]),
    ("maintenance log", ["maintenance log"]), ("work instruction", ["work instruction"]),
    ("compliance memo", ["compliance memo", "ehs memo"]),
    ("regulatory notice", ["decreto regionale", "circolare regionale", "regional decree", "arapo"]),
    ("customer claim", ["customer claim"]), ("customer specification", ["supplier quality requirements"]),
    ("quality note", ["quality note", "qa note"]), ("quality agreement", ["quality agreements"]),
    ("quality plan", ["acceptance criteria"]),
    ("recipe", ["recipe card", "standard operating procedure", "qc release plan"]),
    ("meeting minutes", ["minutes", "verbale"]), ("invoice", ["fattura", "invoice n."]),
    ("calibration certificate", ["calibration certificate"]), ("waste manifest", ["waste transport"]),
    ("training record", ["training record"]), ("audit report", ["internal audit"]),
    ("technical data sheet", ["technical data sheet"]), ("safety data sheet", ["safety data sheet"]),
    ("portfolio memo", ["portfolio memo"]), ("letter", ["termination of", "quality department", "we apologise"]),
]
PRIMARY = {"deviation report", "incident report", "near-miss report", "change request", "lab test report",
           "supplier qualification", "equipment record", "regulatory notice", "compliance memo", "customer claim",
           "customer specification", "quality note", "quality agreement", "work instruction", "audit report"}

ORG_RE = re.compile(r"\b([A-Z][A-Za-z\-]+(?: [A-Z][A-Za-z\-]+){0,3}) (S\.p\.A\.|S\.r\.l\.|GmbH|AB|S\.n\.c\.)")
EQUIP_RE = re.compile(r"\b(?:D-\d|HB-1|VD-1|MS-1|OV-1|FL-\d|SC-2B?|WS-10|VS-1|T-\d|XRF-01|M[25])\b")
REG_RE = re.compile(r"(?:D\.R\.|Decreto Regionale n\.|Regional Decree|Circolare regionale) ?\d+/\d{4}", re.I)
PRODUCT_RE = re.compile(r"\b(?:AF-12|EF-210|TL-5|BW-90|CR-55|H-21|H-30|KO-Epox 410 LC|KO-410|ALTAREP E-19|PS-400|NP-310|CL-77|ZP-40)\b")
IT_WORDS = {"il", "la", "che", "di", "del", "della", "non", "per", "con", "sono", "lotto", "turno"}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
MONTHS.update({m: i + 1 for i, m in enumerate(
    ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"])})
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})


def find_date(text: str) -> str | None:
    t = fold(text[:700])
    m = re.search(r"\b(\d{1,2}) ([a-z]{3,9}) ((?:19|20)\d{2})\b", t)
    if m and m.group(2) in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-]((?:19|20)?\d{2})\b", t)
    if m:
        y = int(m.group(3))
        y = y + (1900 if y > 50 else 2000) if y < 100 else y
        mo, d = int(m.group(2)), int(m.group(1))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y}-{mo:02d}-{d:02d}"
    m = re.search(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b", t)
    if m:
        return m.group(0)
    return None


@lru_cache(maxsize=1)
def _material_aliases() -> list[str]:
    from . import archive

    out = []
    for m in archive.materials().values():
        out += [a for a in m["aliases"] if len(a) > 3]
    out += ["lead chromate", "chromate pigment", "chlorinated rubber", "white topcoat", "hardener", "big-bag", "liner",
            "cans", "impeller", "hydraulic", "warehouse M2", "scale"]
    return out


def entities_in(text: str) -> list[str]:
    ents = set()
    for m in ORG_RE.finditer(text):
        ents.add(m.group(0))
    for rx in (EQUIP_RE, REG_RE, PRODUCT_RE):
        for m in rx.finditer(text):
            ents.add(m.group(0))
    ft = fold(text)
    for a in _material_aliases():
        if fold(a) in ft:
            ents.add(a)
    return sorted(ents)


def metadata(acc: str, text: str) -> dict:
    head = fold(text[:500])
    doc_type = "other"
    if re.search(r"^from: .*\n?.*to:", fold(text[:200]), re.M) or ("subject:" in head and "from:" in head):
        doc_type = "email"
    else:
        for name, keys in DOC_TYPES:
            if any(k in head for k in keys):
                doc_type = name
                break
        if doc_type == "other" and ("turno" in head or "f. bellone" in fold(text[-200:])):
            doc_type = "logbook page"
    refs = sorted(set(DOC_REF.findall(text)))
    own = [r for r in refs if r in text[:260]]
    toks = tokens(text, keep_stop=True)
    lang = "it" if sum(t in IT_WORDS for t in toks) > max(3, len(toks) * 0.04) else "en"
    body = [ln for ln in text.splitlines() if len(ln) > 40]
    title = next((ln.strip() for ln in text.splitlines()[:6] if ln.isupper() and len(ln) > 8), None)
    return {
        "doc_type": doc_type, "date": find_date(text), "title": title, "language": lang,
        "reference_numbers": own, "referenced_documents": [r for r in refs if r not in own],
        "organizations": sorted({m.group(0) for m in ORG_RE.finditer(text)}),
        "materials": [a for a in _material_aliases() if fold(a) in fold(text)][:12],
        "equipment": sorted(set(EQUIP_RE.findall(text))), "products": sorted(set(PRODUCT_RE.findall(text))),
        "regulations": sorted({m.group(0) for m in REG_RE.finditer(text)}), "people": [],
        "summary": (body[0][:200] if body else ""), "suspicious_instructions": injection_suspect(text),
    }


# ----------------------------------------------------------------------------
# investigation heuristics
# ----------------------------------------------------------------------------
REASON_CUES = ["reason", "because", "caused", "cause", "to prevent", "following", "due to", "motivo", "per evitare",
               "d'ora in poi", "from now on", "until", "requires", "require", "change:", "prevents", "to avoid", "mandatory",
               "as a corrective", "recommend", "applies because", "trovati", "neutralis"]
END_CUES = ["replaced", "replaces", "discontinued", "no longer", "ends on", "ended", "terminated", "repealed", "removed",
            "dedicated", "only empty", "not sensitive", "no inert gas", "not measurable", "no change", "no hardener",
            "no livering", "no measurable effect", "is gone", "were removed", "will be removed", "phase-out", "has been corrected",
            "free-flowing", "no lumps", "none detectable", "not detectable", "no hydraulic", "no white", "rely on the supplier",
            "not renewed", "since m5", "all finished goods are stored in m5"]
HOLD_CUES = ["still", "continues", "keep", "stays", "remains", "required", "planned", "same type", "as long as",
             "must be below", "is needed", "need", "legal requirement", "valid until", "require"]
HAZARD_CUES = ["fire", "spark", "burn", "injur", "dizzy", "overcome", "alarm", "blown", "explos", "flammable", "pinhole",
               "claim", "fragments", "foreign", "lost eur", "trucioli", "iron", "lel", "vapour", "flash point"]


def _cues(text: str, cues: list[str]) -> int:
    t = fold(text)
    return sum(1 for c in cues if c in t)


def _step_terms(step_text: str) -> list[str]:
    toks = tokens(step_text)
    return [t for t in toks if not re.fullmatch(r"[\d\.,]+", t) and t not in {"approx", "max", "min", "record", "per",
                                                                             "rm-101", "rm-110"}]


REASON_TYPES = {"change request", "deviation report", "incident report", "near-miss report", "work instruction",
                "logbook page", "lab test report", "customer claim", "customer specification", "regulatory notice",
                "compliance memo", "quality note"}
SPEC_TYPES = {"technical data sheet", "quality plan", "quality note", "safety data sheet"}


def read(p: dict) -> dict:
    terms = set(_step_terms(p["step_text"]))
    key = set(p.get("key_terms") or list(terms)[:5])
    focus = [fold(x) for x in p.get("focus", []) if x]
    purpose = p["purpose"]
    evidence, refs, queries, suspicious = [], [], [], []
    for ps in p["passages"]:
        text = ps["text"]
        if injection_suspect(text):
            suspicious.append(ps["id"])
        ptoks = set(tokens(text))
        ft = fold(text)
        khits, hits = len(key & ptoks), len(terms & ptoks)
        fhits = sum(1 for f in focus if f in ft)
        if purpose == "origin":
            relevant = khits >= 2 or (khits >= 1 and hits >= 3)
        elif purpose == "status":
            relevant = fhits >= 1 or khits >= 2
        else:
            relevant = khits >= 2 or (khits >= 1 and fhits >= 1)
        if not relevant:
            evidence.append({"passage_id": ps["id"], "relevant": False, "stance": "context", "claim": "", "quote": "",
                             "entities": []})
            continue
        sents = [x for x in sentences(text) if not injection_suspect(x)] or sentences(text) or [norm(text)]
        if purpose == "origin":
            cue_list = REASON_CUES
        elif purpose == "status":
            cue_list = END_CUES + HOLD_CUES
        else:
            cue_list = HAZARD_CUES + HOLD_CUES

        def sscore(x):
            xt, xf = set(tokens(x)), fold(x)
            return 2 * len(xt & key) + len(xt & terms) + 2 * sum(1 for f in focus if f in xf) + 0.7 * _cues(x, cue_list)

        best = max(sents, key=sscore)
        words = best.split()
        quote = " ".join(words[:25])
        dt = ps.get("doc_type") or ""
        r, e, h, z = _cues(text, REASON_CUES), _cues(text, END_CUES), _cues(text, HOLD_CUES), _cues(text, HAZARD_CUES)
        if purpose == "origin":
            if dt in REASON_TYPES and (r or z):
                stance = "reason"
            elif dt in SPEC_TYPES or not r:
                stance = "context"
            else:
                stance = "reason"
        elif purpose == "status":
            if z and h and (ps.get("date") or "0") >= "2010":
                stance = "counter"
            else:
                stance = "status" if (e or h) else "context"
        else:
            stance = "counter" if z or h else "context"
        ents = entities_in(text)
        year = f" ({ps['date'][:4]})" if ps.get("date") else ""
        evidence.append({"passage_id": ps["id"], "relevant": True, "stance": stance,
                         "claim": f"{dt.capitalize() or 'Document'}{year}: {' '.join(words[:22])}", "quote": quote,
                         "entities": ents[:8]})
        own = set(DOC_REF.findall(text[:200]))
        refs += [x for x in DOC_REF.findall(text) if x not in own]
        if stance == "reason":
            for ent in ents[:4]:
                queries.append({"query": ent, "purpose": "status"})
    seen = set()
    refs = [x for x in refs if not (x in seen or seen.add(x))]
    return {"evidence": evidence, "follow_up": {"open_refs": refs[:6], "queries": queries[:6]},
            "suspicious_passages": suspicious}


def conclude(p: dict) -> dict:
    ev = p["evidence"]
    step_f = fold(p["step_text"])
    key = set(_step_terms(p["step_text"]))
    reason = [e for e in ev if e["stance"] == "reason" and (e.get("doc_type") or "") in REASON_TYPES]
    status = [e for e in ev if e["stance"] == "status"]
    counter = [e for e in ev if e["stance"] == "counter"]
    spec = [e for e in ev if (e.get("doc_type") or "") in SPEC_TYPES and len(set(tokens(e["quote"])) & key) >= 2]
    out = {"verdict": "UNKNOWN", "reason": "", "origin_year": None, "origin_evidence": [], "chain": [],
           "dependencies": [], "counter_evidence": [], "open_questions": []}
    if not reason:
        if spec:
            out.update(verdict="ACTIVE", reason="The current product documentation states the function of this step.",
                       chain=[{"claim": e["claim"], "evidence": [e["id"]]} for e in spec[:2]])
        else:
            out["open_questions"] = ["No record explaining why this step was introduced was found."]
        return out
    years = [int(e["date"][:4]) for e in reason if e.get("date")]
    origin_year = min(years) if years else None
    out["origin_year"] = origin_year
    out["origin_evidence"] = [e["id"] for e in sorted(reason, key=lambda e: e.get("date") or "9999")[:2]]

    dep_names: list[str] = []
    for e in reason:
        for ent in e.get("entities", []):
            fe = fold(ent)
            if fe in step_f or re.fullmatch(r"(af-12|ef-210|tl-5|sop-07|qp-02)", fe) or ent in dep_names:
                continue
            dep_names.append(ent)
    deps = []
    for name in dep_names[:5]:
        fname = fold(name)
        mention = [e for e in status + counter if fname in fold(e["quote"] + " " + " ".join(e.get("entities", [])))]
        later = [e for e in mention if not origin_year or (e.get("date") and int(e["date"][:4]) >= origin_year)]
        holds, used = None, []
        for e in sorted(later, key=lambda e: e.get("date") or ""):
            if _cues(e["quote"], END_CUES):
                holds, used = False, [e["id"]]
            elif _cues(e["quote"], HOLD_CUES):
                holds, used = True, [e["id"]]
        deps.append({"name": name, "type": "other", "holds": holds, "evidence": used, "note": ""})
    hazard_reason = [e for e in reason if _cues(e["quote"] + " " + e["claim"], HAZARD_CUES)]
    fence_now = [e for e in counter if (e.get("date") or "0") >= "2010" and _cues(e["quote"], HAZARD_CUES + HOLD_CUES)]
    ended = [d for d in deps if d["holds"] is False]
    holding = [d for d in deps if d["holds"] is True]
    chain = [{"claim": e["claim"], "evidence": [e["id"]]} for e in sorted(reason, key=lambda e: e.get("date") or "")[:3]]
    out["dependencies"] = deps
    if fence_now or (hazard_reason and (holding or not ended)):
        out["verdict"] = "FENCE"
        out["reason"] = "Introduced after a safety or quality problem; the archive indicates the hazard is still present."
        chain += [{"claim": e["claim"], "evidence": [e["id"]]} for e in fence_now[:2]]
    elif ended:
        out["verdict"] = "FOSSIL"
        out["reason"] = "The documented reason depended on conditions that later documents show have ended."
        for d in deps:
            if d["holds"] is True:
                d["holds"] = None  # entity still in use, but not the cause of the step
        chain += [{"claim": e["claim"], "evidence": [e["id"]]} for e in status
                  if any(e["id"] in d["evidence"] for d in ended)][:3]
        out["counter_evidence"] = [{"claim": e["claim"], "evidence": [e["id"]], "resolved": True,
                                    "resolution": "Superseded by later evidence that the condition ended."} for e in counter[:2]]
    elif holding:
        out["verdict"] = "ACTIVE"
        out["reason"] = "The documented reason still applies."
        chain += [{"claim": e["claim"], "evidence": [e["id"]]} for e in status[:2]]
    else:
        out["open_questions"] = ["A reason was found but the archive does not show whether it still applies."]
    out["chain"] = chain
    return out


# ----------------------------------------------------------------------------
# other tasks
# ----------------------------------------------------------------------------
ACTION_WORDS = [("remove", ["remove", "drop", "eliminate", "delete", "stop", "skip", "without"]),
                ("shorten", ["shorten", "shorter", "cut the", "from 30 to", "from 60 to", "reduce the wait", "reduce the hold"]),
                ("reduce", ["reduce", "lower", "less", "keep them 1 year", "1 year"]),
                ("switch_supplier", ["supplier", "cheaper", "switch"]),
                ("substitute_material", ["replace", "substitute", "instead of"]),
                ("replace_equipment", ["new impeller", "replace the disperser", "new equipment"])]


def change_parse(p: dict) -> dict:
    text = p["proposal"]
    ids = [m.upper() for m in STEP_ID.findall(text)]
    ft = fold(text)
    action = "other"
    for name, words in ACTION_WORDS:
        if any(w in ft for w in words):
            action = name
            break
    if not ids:
        qt = set(tokens(text))
        scored = []
        for s in p["steps"]:
            st = set(_step_terms(s["instruction"]))
            scored.append((len(qt & st), s["id"]))
        scored.sort(reverse=True)
        if scored and scored[0][0] >= 2:
            ids = [scored[0][1]]
    subject = next((a for a in _material_aliases() if fold(a) in ft), "")
    if action in ("switch_supplier", "substitute_material") and subject:
        ids = []
    return {"targets": ids[:3], "action": action, "subject": subject, "from_value": "", "to_value": "",
            "summary": norm(text)[:160]}


def ask_match(p: dict) -> dict:
    ids = [m.upper() for m in STEP_ID.findall(p["question"])]
    if ids:
        return {"step_id": ids[0], "is_question_about_step": True}
    q = fold(p["question"])
    if not any(w in q for w in ("why", "perche", "reason", "what is", "purpose", "do we")):
        return {"step_id": None, "is_question_about_step": False}
    qt = set(tokens(p["question"]))
    best, best_id = 0, None
    for s in p["steps"]:
        o = len(qt & set(_step_terms(s["instruction"])))
        if o > best:
            best, best_id = o, s["id"]
    return {"step_id": best_id if best >= 2 else None, "is_question_about_step": best >= 2}


def ask_answer(p: dict) -> dict:
    qt = tokens(p["question"])
    rel = [ps for ps in p["passages"] if len(set(qt) & set(tokens(ps["text"]))) >= 2][:4]
    if not rel:
        return {"answer": "The archive passages retrieved do not answer this question.", "claims": [],
                "related_steps": [], "insufficient_evidence": True}
    claims = [{"text": best_sentence(ps["text"], qt), "evidence": [ps["id"]]} for ps in rel[:3]]
    return {"answer": " ".join(c["text"] for c in claims)[:700], "claims": claims, "related_steps": [],
            "insufficient_evidence": False}


def trial_draft(p: dict) -> dict:
    st = p["step"]
    return {
        "title": f"Controlled trial: run {st['process_code']} without step {st['id']}",
        "objective": f"Confirm that '{st['instruction']}' can be removed without effect on quality or safety, as the archive "
                     f"evidence suggests ({p['verdict'].get('reason', '')}).",
        "scope": f"{st['process_code']}: 10 consecutive production batches on the usual equipment, step {st['id']} omitted.",
        "duration": "4 weeks, plus 12 weeks of retained-sample monitoring",
        "measurements": ["All release tests of QP-02 on every trial batch",
                         "Accelerated storage stability (40 °C) on retained samples",
                         "Customer complaints on trial lots for 6 months"],
        "acceptance_criteria": ["All trial batches pass release on the first attempt",
                                "No difference beyond method repeatability versus the previous 20 batches",
                                "No safety event or alarm attributable to the change"],
        "rollback": f"Reinstate step {st['id']} immediately on any out-of-specification result; quarantine affected lots.",
        "risks": ["Hidden reason not documented in the archive", "Interaction with other steps of the recipe"],
        "approvals": ["Process engineer", "QC laboratory head", "EHS manager", "Plant manager"],
    }


def run(task: str, payload: dict) -> dict:
    if task == "extract.metadata":
        return metadata(payload["acc"], payload["text"])
    if task == "investigate.read":
        return read(payload)
    if task == "investigate.conclude":
        return conclude(payload)
    if task == "change.parse":
        return change_parse(payload)
    if task == "ask.match":
        return ask_match(payload)
    if task == "ask.answer":
        return ask_answer(payload)
    if task == "trial.draft":
        return trial_draft(payload)
    if task == "tripwire.assess":
        return {"effects": [{"step_id": c["step_id"], "effect": c["rule_effect"], "explanation": c["rule_explanation"],
                             "evidence": c.get("evidence_ids", [])[:2]} for c in payload["candidates"]]}
    raise KeyError(task)


def run_text(task: str, user: str) -> str:
    return "OK (offline fixture provider)"
