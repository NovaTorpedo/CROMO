"""Tripwires: forward-looking alerts when a change event touches a recovered reason.

Every verdict records the dependencies its reason relies on. When a change event
arrives (supplier switch, material substitution, equipment replacement, regulation
change, step removal) CROMO finds the affected steps:

  fence_dependency_removed  a FENCE whose protected hazard goes away -> may become a fossil (re-investigate, trial)
  fence_still_required      a FENCE touched by the change that still protects something present
  fossil_reactivated        a FOSSIL whose original problem comes back -> the step is needed again
  becomes_fossil            an ACTIVE step whose reason the change removes
  review_required           the step uses the changed item

Candidate selection and the default effect are deterministic (term matching with the
material master); in live mode the reasoning model reviews each candidate and may
refine the effect, within guard rules (a FENCE can never be declared removable here).
"""

from __future__ import annotations

import json
import time
import uuid

from . import archive, db, investigate, llm
from .schemas import TripwireOut
from .text import STEP_ID, fold, tokens

GENERIC = {"grade", "type", "standard", "new", "old", "allowed", "removed", "solvent", "agent", "process", "step",
           "liquid", "addition", "use", "used"}


def _expand(text: str) -> set[str]:
    """Tokens of `text` plus the aliases of any material it names."""
    toks = set(tokens(text)) - GENERIC
    ft = fold(text)
    for m in archive.materials().values():
        names = [m["name"]] + m["aliases"]
        if any(fold(a) in ft for a in names if len(a) > 3):
            for a in names:
                toks |= set(tokens(a)) - GENERIC
    return toks


def _match(a: set[str], text: str) -> float:
    b = set(tokens(text)) - GENERIC
    if not a or not b:
        return 0.0
    inter = a & b
    return len(inter) / min(len(a), 4)


def registry() -> list[dict]:
    out = []
    for sid, v in sorted(investigate.all_stored().items()):
        for d in v.get("dependencies", []):
            out.append({"step_id": sid, "verdict": v["verdict"], "dependency": d["name"], "type": d.get("type"),
                        "holds": d.get("holds"), "evidence": d.get("evidence", []), "instruction": v["instruction"]})
    return out


def _evidence_text(v: dict) -> str:
    return " ".join(e.get("quote", "") + " " + " ".join(e.get("entities", [])) for e in v.get("evidence", {}).values())


def candidates(event: dict) -> list[dict]:
    verdicts = investigate.all_stored()
    frm, to = _expand(event.get("from", "")), _expand(event.get("to", ""))
    removed_step = None
    if event.get("type") == "step_removal":
        m = STEP_ID.search(event.get("from", ""))
        removed_step = m.group(0).upper() if m else None
    out = []
    for sid, v in sorted(verdicts.items()):
        if event.get("process") and v["process"] != event["process"] and event.get("type") != "step_removal":
            pass  # changes can cross processes (shared materials); keep but rank lower
        deps = v.get("dependencies", [])
        instr = v["instruction"]
        effect, why, ids = None, "", []
        if removed_step:
            if sid == removed_step:
                continue
            rs = archive.step(removed_step)
            rs_terms = _expand(rs["instruction"])
            for d in deps:
                if d.get("holds") and (removed_step in d["name"].upper() or _match(rs_terms, d["name"]) >= 0.5):
                    effect, ids = "becomes_fossil", d.get("evidence", [])
                    why = f"Its reason depends on '{d['name']}', which the change removes."
                    break
            if not effect and v["verdict"] in ("ACTIVE", "FENCE") and _match(rs_terms, _evidence_text(v)) >= 0.75:
                effect, why = "review_required", "Its evidence refers to what the removed step adds."
        else:
            dep_from = [d for d in deps if _match(frm, d["name"]) >= 0.5]
            dep_to = [d for d in deps if d.get("holds") is False and _match(to, d["name"]) >= 0.75]
            if v["verdict"] == "FOSSIL" and not dep_to:
                # does the new situation bring back the original problem described in the cited evidence?
                to_plain = set(tokens(event.get("to", ""))) - GENERIC
                cited = {i for c in v.get("chain", []) for i in c.get("evidence", [])}
                ended_names = [fold(d["name"]) for d in deps if d.get("holds") is False]
                ctx = set()
                for i, e in v.get("evidence", {}).items():
                    q = e.get("quote", "")
                    if (i in cited and e.get("stance") == "reason") or any(n and n in fold(q) for n in ended_names):
                        ctx |= set(tokens(q))
                for d in deps:
                    ctx |= set(tokens(d["name"]))
                hit = to_plain & ctx
                novel = hit - set(tokens(instr))
                if to_plain and len(hit) >= max(2, 0.6 * len(to_plain)) and novel:
                    dep_to = [d for d in deps if d.get("holds") is False] or [{"name": ", ".join(sorted(novel)), "evidence": list(cited)[:2]}]
            uses = _match(frm, instr) >= 0.5
            ev_hit = _match(frm, _evidence_text(v)) >= 0.5
            if v["verdict"] == "FOSSIL" and dep_to:
                effect, ids = "fossil_reactivated", dep_to[0].get("evidence", [])
                why = f"The new situation brings back '{dep_to[0]['name']}', the problem this step was introduced for."
            elif v["verdict"] == "FENCE" and (dep_from or ev_hit):
                other = [d for d in deps if d not in dep_from and d.get("holds")]
                if dep_from and not other:
                    effect, ids = "fence_dependency_removed", dep_from[0].get("evidence", [])
                    why = (f"This fence protects against a hazard tied to '{dep_from[0]['name']}'. The change removes it: the "
                           "step may become a fossil - re-investigate and trial before any removal.")
                else:
                    effect = "fence_still_required"
                    ids = (other[0].get("evidence", []) if other else [])
                    why = ("The change touches this fence, but it still protects against "
                           f"'{other[0]['name']}'." if other else "The change touches this fence; its protective reason remains.")
            elif v["verdict"] == "ACTIVE" and dep_from and all(d.get("holds") for d in dep_from) and len(deps) == len(dep_from):
                effect, ids = "becomes_fossil", dep_from[0].get("evidence", [])
                why = f"Its only documented reason, '{dep_from[0]['name']}', is removed by the change."
            elif uses:
                effect, why = "review_required", "The step uses the item that changes."
        if effect:
            out.append({"step_id": sid, "verdict": v["verdict"], "strength": v["strength"]["grade"], "instruction": instr,
                        "reason": v.get("reason", ""), "dependencies": deps, "rule_effect": effect,
                        "rule_explanation": why, "evidence_ids": ids})
    return out


GUARD = {"FENCE": {"fence_dependency_removed", "fence_still_required", "review_required"},
         "FOSSIL": {"fossil_reactivated", "review_required", "no_effect"},
         "ACTIVE": {"becomes_fossil", "review_required", "no_effect"},
         "UNKNOWN": {"review_required", "no_effect"}}


async def evaluate(event: dict, *, store: bool = True) -> dict:
    t0 = time.perf_counter()
    cands = candidates(event)
    effects = {c["step_id"]: {"effect": c["rule_effect"], "explanation": c["rule_explanation"], "evidence": c["evidence_ids"]}
               for c in cands}
    if cands and llm.mode() == "amd":
        try:
            res = await llm.run_task("tripwire.assess", {"event": event, "candidates": [
                {k: c[k] for k in ("step_id", "verdict", "instruction", "reason", "dependencies", "rule_effect")} for c in cands]},
                TripwireOut)
            for e in res.effects:
                c = next((c for c in cands if c["step_id"] == e.step_id), None)
                if c and e.effect in GUARD.get(c["verdict"], set()):
                    effects[e.step_id] = {"effect": e.effect, "explanation": e.explanation or c["rule_explanation"],
                                          "evidence": [i for i in e.evidence if i in c.get("evidence_ids", [])] or c["evidence_ids"]}
        except llm.ProviderError:
            pass
    verdicts = investigate.all_stored()
    alerts = []
    sev = {"fossil_reactivated": 0, "fence_dependency_removed": 1, "becomes_fossil": 2, "fence_still_required": 3,
           "review_required": 4}
    for sid, e in effects.items():
        if e["effect"] == "no_effect":
            continue
        v = verdicts[sid]
        alerts.append({"step_id": sid, "verdict": v["verdict"], "instruction": v["instruction"], "process": v["process"],
                       "effect": e["effect"], "explanation": e["explanation"],
                       "evidence": [v["evidence"][i] for i in e["evidence"] if i in v.get("evidence", {})][:2],
                       "annual_cost_eur": v["cost"]["annual_eur"]})
    alerts.sort(key=lambda a: (sev.get(a["effect"], 9), a["step_id"]))
    rec = {"id": uuid.uuid4().hex[:10], "event": event, "alerts": alerts, "created_at": time.time(),
           "provider": llm.mode(), "duration_s": round(time.perf_counter() - t0, 2)}
    if store:
        db.ex("INSERT INTO change_events(id, event_json, alerts_json, created_at) VALUES(?,?,?,?)",
              (rec["id"], json.dumps(event), json.dumps(alerts), rec["created_at"]))
    return rec


PRESETS = [
    {"id": "solvent", "label": "Letdown solvent: white spirit -> high-flash isoparaffin", "event": {
        "type": "material_substitution", "process": "ALK", "from": "white spirit D40",
        "to": "high-flash isoparaffin solvent (flash point 62 °C)"}},
    {"id": "resin", "label": "Epoxy resin: KO-Epox 410 LC -> cheaper standard grade", "event": {
        "type": "supplier_switch", "process": "EPX", "from": "KO-Epox 410 LC (Kessler-Ondra)",
        "to": "standard grade liquid epoxy resin (crystallising type)"}},
    {"id": "impeller", "label": "Disperser D-4: steel impeller -> ceramic-coated", "event": {
        "type": "equipment_replacement", "process": "TNK", "from": "D-4 mild steel impeller", "to": "ceramic-coated impeller (no wear)"}},
    {"id": "organotin", "label": "Regulation: organotin catalysts restricted from 2027", "event": {
        "type": "regulation_change", "process": "TNK", "from": "DBTDL organotin catalyst allowed",
        "to": "organotin catalysts restricted from 2027"}},
    {"id": "nh4cl", "label": "Remove ALK-04 (ammonium chloride) from AF-12", "event": {
        "type": "step_removal", "process": "ALK", "from": "ALK-04 ammonium chloride addition", "to": "removed"}},
    {"id": "cleaner", "label": "Cleaning: acetone -> water-based alkaline cleaner", "event": {
        "type": "material_substitution", "process": "SOL", "from": "acetone", "to": "water-based alkaline cleaner (non-flammable)"}},
]
