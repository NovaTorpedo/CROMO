"""Safe trial plans for fossils, approved through an Evolus workflow.

CROMO never deletes a step. For a FOSSIL it drafts a controlled trial (scope, measurements,
acceptance criteria, rollback) and sends it to an engineer for approval through the Evolus
workflow configured in EVOLUS_TRIAL_WORKFLOW_ID. Status comes back by polling the execution
(or via the webhook). The approval decision is recorded with who/when/source.

Lifecycle: draft -> submitted (Evolus run queued/running) -> awaiting_decision -> approved | rejected
           (failed if the workflow run fails; offline: submitted is simulated and labelled as such)
"""

from __future__ import annotations

import json
import re
import time
import uuid

from . import archive, config, db, evolus, investigate, llm
from .schemas import TrialPlanOut


def _row(r) -> dict:
    d = dict(r)
    d["plan"] = json.loads(d.pop("plan_json"))
    d["history"] = json.loads(d.pop("history_json"))
    return d


def list_trials() -> list[dict]:
    return [_row(r) for r in db.q("SELECT * FROM trials ORDER BY created_at DESC")]


def get(tid: str) -> dict:
    r = db.q1("SELECT * FROM trials WHERE id=?", (tid,))
    if not r:
        raise KeyError("trial not found")
    return _row(r)


def _save(t: dict) -> None:
    db.ex("INSERT OR REPLACE INTO trials(id, step_id, plan_json, status, evolus_execution_id, history_json, created_at, updated_at) "
          "VALUES(?,?,?,?,?,?,?,?)", (t["id"], t["step_id"], json.dumps(t["plan"], ensure_ascii=False), t["status"],
                                      t.get("evolus_execution_id"), json.dumps(t["history"], ensure_ascii=False),
                                      t["created_at"], time.time()))


def _event(t: dict, status: str, note: str, source: str = "cromo", **extra) -> None:
    t["status"] = status
    t["history"].append({"status": status, "note": note, "source": source, "ts": time.time(), **extra})


async def draft(step_id: str) -> dict:
    v = investigate.stored(step_id)
    if not v:
        raise ValueError("Investigate the step first.")
    if v["verdict"] != "FOSSIL":
        raise ValueError(f"Trials are only drafted for FOSSIL steps (this step is {v['verdict']}).")
    st = archive.step(step_id)
    ev = [{"claim": c["claim"], "sources": [v["evidence"][i]["acc"] for i in c["evidence"] if i in v["evidence"]]}
          for c in v["chain"]]
    payload = {"step": {k: st[k] for k in ("id", "instruction", "process", "process_code", "process_name")},
               "verdict": {"reason": v.get("reason"), "strength": v["strength"]["grade"], "evidence": ev,
                           "dependencies": v.get("dependencies", []), "counter_evidence": v.get("counter_evidence", [])},
               "annual_cost_eur": v["cost"]["annual_eur"]}
    plan = await llm.run_task("trial.draft", payload, TrialPlanOut)
    t = {"id": "TR-" + uuid.uuid4().hex[:6].upper(), "step_id": step_id, "plan": {
        **plan.model_dump(), "step": payload["step"], "verdict": v["verdict"], "strength": v["strength"]["grade"],
        "annual_saving_eur": v["cost"]["annual_eur"], "evidence": ev[:5], "drafted_by": llm.model_name("reasoner")},
        "status": "draft", "history": [], "created_at": time.time(), "evolus_execution_id": None}
    _event(t, "draft", f"Trial plan drafted by {llm.model_name('reasoner')}.")
    _save(t)
    return t


def plan_text(t: dict) -> str:
    p = t["plan"]
    lines = [f"CROMO TRIAL PLAN {t['id']} - {p['title']}", "",
             f"Step: {p['step']['id']} ({p['step']['process_code']}): {p['step']['instruction']}",
             f"Verdict: FOSSIL ({p['strength']} evidence). Potential saving: EUR {p['annual_saving_eur']:,}/year.", "",
             f"Objective: {p['objective']}", f"Scope: {p['scope']}", f"Duration: {p['duration']}", "", "Measurements:"]
    lines += [f"- {m}" for m in p["measurements"]] + ["", "Acceptance criteria:"]
    lines += [f"- {a}" for a in p["acceptance_criteria"]] + ["", f"Rollback: {p['rollback']}", "", "Risks:"]
    lines += [f"- {r}" for r in p["risks"]] + ["", "Evidence (archive accession numbers):"]
    lines += [f"- {e['claim']} [{', '.join(e['sources'])}]" for e in p["evidence"]]
    lines += ["", "Required approvals: " + ", ".join(p["approvals"]),
              "Reply APPROVED or REJECTED with your name. CROMO never removes a step without approval."]
    return "\n".join(lines)


async def submit(tid: str) -> dict:
    t = get(tid)
    if t["status"] not in ("draft", "failed"):
        raise ValueError("Trial already submitted.")
    s = config.settings
    if s.evolus_configured and s.evolus_trial_workflow_id:
        try:
            res = await evolus.run_workflow(
                s.evolus_trial_workflow_id, plan_text(t),
                parameters={"trial_id": t["id"], "step_id": t["step_id"], "process": t["plan"]["step"]["process_code"]},
                files={"file": (f"{t['id']}.txt", plan_text(t).encode("utf-8"), "text/plain")})
            t["evolus_execution_id"] = res.get("executionId")
            _event(t, "submitted", "Sent to the Evolus approval workflow.", "evolus", execution_id=res.get("executionId"))
        except evolus.EvolusError as e:
            _event(t, "failed", f"Evolus workflow could not be started: {e}", "evolus")
    else:
        _event(t, "submitted", "Evolus workflow not configured: submission simulated locally (offline mode).", "offline")
        _event(t, "awaiting_decision", "Waiting for the engineer's decision (simulated, offline).", "offline")
    _save(t)
    return t


DECISION_RE = re.compile(r"\b(APPROVED|REJECTED|APPROVATO|RESPINTO)\b", re.I)


async def refresh(tid: str) -> dict:
    t = get(tid)
    s = config.settings
    if t["status"] not in ("submitted", "awaiting_decision") or not t.get("evolus_execution_id"):
        return t
    try:
        ex = await evolus.get_execution(s.evolus_trial_workflow_id, t["evolus_execution_id"])
    except evolus.EvolusError as e:
        _event(t, t["status"], f"Status check failed: {e}", "evolus")
        _save(t)
        return t
    status = str(ex.get("status", "")).lower()
    out = json.dumps(ex.get("output") or ex.get("result") or ex, ensure_ascii=False)[:4000]
    if status == "failed":
        _event(t, "failed", "Evolus workflow run failed.", "evolus")
    elif status == "completed":
        m = DECISION_RE.search(out)
        if m:
            approved = m.group(1).upper() in ("APPROVED", "APPROVATO")
            _event(t, "approved" if approved else "rejected", "Decision returned by the Evolus workflow.", "evolus",
                   output_excerpt=out[:600])
        elif t["status"] != "awaiting_decision":
            _event(t, "awaiting_decision", "Evolus workflow completed: approval request delivered to the engineer.", "evolus",
                   output_excerpt=out[:600])
    _save(t)
    return t


def decide(tid: str, approved: bool, by: str, note: str = "") -> dict:
    t = get(tid)
    if t["status"] not in ("submitted", "awaiting_decision"):
        raise ValueError("Trial is not awaiting a decision.")
    by = re.sub(r"[^\w .'\-]", "", by or "")[:60] or "engineer"
    _event(t, "approved" if approved else "rejected", (note or "")[:300] or ("Approved" if approved else "Rejected"),
           "engineer", by=by)
    _save(t)
    return t


def webhook(execution_id: str, payload: dict) -> dict | None:
    r = db.q1("SELECT id FROM trials WHERE evolus_execution_id=?", (execution_id,))
    if not r:
        return None
    t = get(r["id"])
    out = json.dumps(payload, ensure_ascii=False)[:4000]
    m = DECISION_RE.search(out)
    if m:
        approved = m.group(1).upper() in ("APPROVED", "APPROVATO")
        _event(t, "approved" if approved else "rejected", "Decision delivered by Evolus webhook.", "evolus")
    else:
        _event(t, "awaiting_decision", "Evolus webhook: approval request delivered.", "evolus")
    _save(t)
    return t
