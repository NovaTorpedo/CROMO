"""Citation validation, safety guards and the transparent evidence-strength rules."""

from __future__ import annotations

from .schemas import ConcludeOut

PRIMARY = {"deviation report", "incident report", "near-miss report", "change request", "lab test report",
           "supplier qualification", "equipment record", "regulatory notice", "compliance memo", "customer claim",
           "customer specification", "quality note", "quality agreement", "work instruction", "audit report",
           "portfolio memo"}
HAZARD_WORDS = ("fire", "spark", "burn", "injur", "dizzy", "overcome", "alarm", "blown", "explos", "flammable", "pinhole",
                "claim", "fragment", "foreign", "lel", "vapour", "vapor", "toxic", "corrosion", "safety")
RECENT_YEAR = 2016  # "recent" = within the last 10 years of the archive (2026)


def _clean_ids(ids: list[str], valid: dict) -> list[str]:
    seen, out = set(), []
    for i in ids or []:
        i = str(i).strip()
        if i in valid and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def validate(out: ConcludeOut, evidence: dict[str, dict]) -> tuple[dict, list[str], int]:
    """Drop uncited claims and unknown ids; apply verdict guards. Returns (verdict dict, guard notes, removed count)."""
    valid = {k: v for k, v in evidence.items() if v.get("verified") and not v.get("suspicious")}
    notes: list[str] = []
    removed = 0
    chain = []
    for c in out.chain:
        ids = _clean_ids(c.evidence, valid)
        if ids:
            chain.append({"claim": c.claim, "evidence": ids})
        else:
            removed += 1
    deps = []
    for d in out.dependencies:
        ids = _clean_ids(d.evidence, valid)
        holds = d.holds if ids else None
        if d.holds is not None and not ids:
            notes.append(f"Status of dependency '{d.name}' was asserted without evidence and is shown as unknown.")
        deps.append({"name": d.name, "type": d.type, "holds": holds, "evidence": ids, "note": d.note})
    counters = []
    for c in out.counter_evidence:
        ids = _clean_ids(c.evidence, valid)
        if ids:
            counters.append({"claim": c.claim, "evidence": ids, "resolved": bool(c.resolved), "resolution": c.resolution})
        else:
            removed += 1
    origin_ids = _clean_ids(out.origin_evidence, valid)
    verdict = out.verdict
    if removed:
        notes.append(f"{removed} claim(s) without valid citations were removed.")

    def downgrade(msg):
        nonlocal verdict
        notes.append(msg)
        verdict = "UNKNOWN"

    if verdict in ("FOSSIL", "FENCE", "ACTIVE") and not chain:
        downgrade(f"{out.verdict} was proposed but no claim is supported by verified evidence: routed to a human (UNKNOWN).")
    if verdict == "FOSSIL":
        ended = [d for d in deps if d["holds"] is False]
        holding = [d for d in deps if d["holds"] is True]
        hazards = [c for c in counters if not c["resolved"]
                   and any(w in (c["claim"] + " ".join(evidence[i]["quote"] for i in c["evidence"])).lower() for w in HAZARD_WORDS)]
        if not ended:
            downgrade("FOSSIL requires evidence that the original condition ended; none was verified.")
        elif holding:
            downgrade("FOSSIL rejected: at least one dependency of the reason still holds.")
        elif hazards:
            downgrade("FOSSIL rejected: unresolved safety/quality counter-evidence - possible FENCE, human review required.")
    if verdict == "FENCE" and not any(d["holds"] is True for d in deps) and not counters:
        notes.append("FENCE kept: protective reason documented, but no evidence that its dependency still holds was verified.")
    result = {
        "verdict": verdict, "proposed_verdict": out.verdict, "reason": out.reason, "origin_year": out.origin_year,
        "origin_evidence": origin_ids, "chain": chain, "dependencies": deps, "counter_evidence": counters,
        "open_questions": out.open_questions,
    }
    return result, notes, removed


def strength(v: dict, evidence: dict[str, dict]) -> dict:
    cited: list[str] = []
    for c in v["chain"]:
        cited += c["evidence"]
    for d in v["dependencies"]:
        cited += d["evidence"]
    for c in v["counter_evidence"]:
        cited += c["evidence"]
    cited += v.get("origin_evidence", [])
    cited = [c for c in dict.fromkeys(cited) if c in evidence]
    docs: dict[str, dict] = {}
    for i in cited:
        e = evidence[i]
        docs.setdefault(e["acc"], e)
    primary = [d for d in docs.values() if (d.get("doc_type") or "") in PRIMARY]
    secondary = [d for d in docs.values() if (d.get("doc_type") or "") not in PRIMARY]
    br = []
    if primary:
        br.append({"label": f"{len(primary)} primary record(s) (reports, change requests, qualifications, notices)",
                   "points": min(8, 2 * len(primary))})
    if secondary:
        br.append({"label": f"{len(secondary)} secondary source(s) (emails, minutes, logbooks, data sheets)",
                   "points": min(3, len(secondary))})
    status_docs = {evidence[i]["acc"] for d in v["dependencies"] for i in d["evidence"]}
    origin_docs = {evidence[i]["acc"] for c in v["chain"][:2] for i in c["evidence"]} | \
                  {evidence[i]["acc"] for i in v.get("origin_evidence", [])}
    if v["verdict"] in ("FOSSIL", "FENCE") and status_docs and origin_docs and status_docs - origin_docs:
        br.append({"label": "Origin and current status confirmed by independent documents", "points": 1})
    years = [int(evidence[i]["date"][:4]) for i in cited if evidence[i].get("date")]
    if years and max(years) >= RECENT_YEAR:
        br.append({"label": f"Recent evidence (latest {max(years)})", "points": 1})
    unresolved = [c for c in v["counter_evidence"] if not c["resolved"]]
    if unresolved:
        br.append({"label": f"{len(unresolved)} unresolved contradiction(s)", "points": -2 * len(unresolved)})
    if len(docs) == 1:
        br.append({"label": "Single source", "points": -1})
    kinds = {(d.get("doc_type") or "") for d in docs.values()}
    if docs and kinds <= {"logbook page", "email", "meeting minutes"}:
        br.append({"label": "Only informal sources (logbook / email / minutes)", "points": -1})
    score = sum(b["points"] for b in br)
    if v["verdict"] == "UNKNOWN":
        grade = "Insufficient"
    elif score >= 7:
        grade = "Strong"
    elif score >= 4:
        grade = "Moderate"
    else:
        grade = "Weak"
    return {"grade": grade, "score": score, "breakdown": br, "documents": len(docs), "cited": cited,
            "rule": "Strong >= 7 points, Moderate 4-6, Weak <= 3; UNKNOWN is always 'Insufficient'."}
