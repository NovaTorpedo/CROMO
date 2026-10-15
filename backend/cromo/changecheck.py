"""'Before you change' - tells people and AI optimisers which fences not to tear down.

Input: a proposed change in plain language (or structured). The reasoning model only
maps the proposal onto steps/materials; the decision itself is made by deterministic,
auditable rules over the recovered verdicts:

  FENCE targeted (remove / shorten / reduce)          -> BLOCKED
  UNKNOWN targeted                                     -> CAUTION (investigate / ask veterans)
  FOSSIL targeted, evidence Strong/Moderate            -> ALLOWED WITH TRIAL (never a direct deletion)
  FOSSIL targeted, evidence Weak                       -> CAUTION
  ACTIVE targeted                                      -> CAUTION (reason still valid)
  material / supplier / equipment changes              -> tripwire analysis: fossil reactivated or fence affected -> CAUTION,
                                                          review only -> ALLOWED WITH REVIEW
  other steps that depend on a targeted step           -> listed (they may become removable too)
"""

from __future__ import annotations

import time

import re

from . import archive, investigate, llm, tripwires
from .schemas import ChangeParseOut
from .text import STEP_ID

ORDER = ["blocked", "caution", "allowed_with_trial", "allowed_with_review", "allowed"]


def _worst(ds: list[str]) -> str:
    return min(ds, key=ORDER.index) if ds else "allowed"


async def check(proposal: str) -> dict:
    t0 = time.perf_counter()
    steps = [{"id": s["id"], "instruction": s["instruction"]} for s in archive.steps()]
    parsed = await llm.run_task("change.parse", {"proposal": proposal, "steps": steps}, ChangeParseOut)
    known = {s["id"] for s in steps}
    targets = [t.upper() for t in parsed.targets if t.upper() in known]
    # step ids written in the proposal always count, whatever the model mapped
    for m in STEP_ID.findall(proposal):
        if m.upper() in known and m.upper() not in targets:
            targets.append(m.upper())
    if (targets and parsed.action in ("other", "substitute_material", "switch_supplier", "replace_equipment")
            and re.search(r"\b(remove|drop|delete|eliminate|skip|stop)\b", proposal, re.I)):
        parsed.action = "remove"
    verdicts = investigate.all_stored()
    findings, decisions = [], []
    for sid in targets:
        v = verdicts.get(sid)
        if not v:
            findings.append({"step_id": sid, "decision": "caution", "why": "Not investigated yet - run the investigation first."})
            decisions.append("caution")
            continue
        g = v["strength"]["grade"]
        if v["verdict"] == "FENCE":
            d = "blocked" if parsed.action in ("remove", "shorten", "reduce", "modify", "other") else "caution"
            why = ("This step is a FENCE: it looks unnecessary but protects against a documented hazard that is still present. "
                   + (v.get("reason") or ""))
        elif v["verdict"] == "UNKNOWN":
            d, why = "caution", "No reliable reason was found for this step. Investigate further or ask experienced staff before changing it."
        elif v["verdict"] == "FOSSIL":
            d = "allowed_with_trial" if g in ("Strong", "Moderate") else "caution"
            why = (f"FOSSIL ({g} evidence): the original reason no longer applies. {v.get('reason') or ''} "
                   "Remove it only through a controlled trial with rollback." if d == "allowed_with_trial" else
                   "Probable fossil, but the evidence is weak: confirm before changing.")
        else:
            d, why = "caution", "ACTIVE step: its reason is documented and still valid. " + (v.get("reason") or "")
        decisions.append(d)
        findings.append({"step_id": sid, "verdict": v["verdict"], "strength": g, "decision": d, "why": why.strip(),
                         "instruction": v["instruction"],
                         "evidence": [v["evidence"][i] for c in v["chain"][:3] for i in c["evidence"][:1] if i in v["evidence"]],
                         "annual_cost_eur": v["cost"]["annual_eur"]})
        # dependent steps (coupled steps)
        if parsed.action == "remove":
            ev = await tripwires.evaluate({"type": "step_removal", "process": v["process"], "from": f"{sid} {v['instruction']}",
                                           "to": "removed"}, store=False)
            for a in ev["alerts"]:
                if a["effect"] == "becomes_fossil":
                    findings.append({"step_id": a["step_id"], "verdict": a["verdict"], "decision": "info",
                                     "why": f"Coupled step: {a['explanation']} If {sid} goes, {a['step_id']} may be removable too "
                                            f"(about EUR {a['annual_cost_eur']:,}/yr).", "instruction": a["instruction"],
                                     "evidence": a["evidence"]})
    if not targets and parsed.subject:
        event = {"type": parsed.action if parsed.action in ("switch_supplier", "substitute_material", "replace_equipment")
                 else "material_substitution", "from": parsed.from_value or parsed.subject, "to": parsed.to_value or proposal}
        ev = await tripwires.evaluate(event, store=False)
        for a in ev["alerts"]:
            d = {"fossil_reactivated": "caution", "fence_dependency_removed": "caution", "fence_still_required": "caution",
                 "becomes_fossil": "allowed_with_review", "review_required": "allowed_with_review"}[a["effect"]]
            decisions.append(d)
            findings.append({"step_id": a["step_id"], "verdict": a["verdict"], "decision": d, "why": a["explanation"],
                             "instruction": a["instruction"], "evidence": a["evidence"], "effect": a["effect"]})
    if not targets and not parsed.subject:
        decisions.append("caution")
        findings.append({"step_id": None, "decision": "caution",
                         "why": "The proposal could not be mapped to a recipe step or material. Please name the step or material."})
    if not decisions or all(f.get("decision") == "info" for f in findings):
        decisions.append("caution")
        findings.append({"step_id": None, "decision": "caution",
                         "why": "CROMO could not identify which steps this change affects, so it cannot clear it. "
                                "Name the step (e.g. SOL-02) or the material/equipment involved."})
    decision = _worst(decisions)
    return {"proposal": proposal, "parsed": parsed.model_dump(), "decision": decision, "findings": findings,
            "provider": llm.mode(), "duration_s": round(time.perf_counter() - t0, 2),
            "policy": "Fences are never removed; fossils only through a controlled trial with rollback; unknowns go to a human."}
