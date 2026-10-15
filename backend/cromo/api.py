"""CROMO HTTP API (FastAPI). Serves the built frontend from frontend/dist.

Read endpoints are public. Endpoints that call models or Evolus (spend GPU time or credits)
or change state require the demo access token when CROMO_ACCESS_TOKEN is set, and are rate
limited. Keys never leave the server.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from . import (archive, ask, changecheck, config, costs, db, evolus, investigate, llm, system, trials, tripwires)
from .security import BodyLimit, SecurityHeaders, rate_limit, require_write, token_ok

STEP_RE = re.compile(r"^(ALK|EPX|SOL|TNK|QC)-\d{2}$")
_live_sem = asyncio.Semaphore(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .cli import _bootstrap

    await _bootstrap()
    yield
    await llm.aclose()


app = FastAPI(title="CROMO", version="0.1.0", lifespan=lifespan, docs_url="/api/docs-ui", redoc_url=None,
              openapi_url="/api/openapi.json")
app.add_middleware(SecurityHeaders)
app.add_middleware(BodyLimit)
if config.settings.allowed_origins:
    app.add_middleware(CORSMiddleware, allow_origins=list(config.settings.allowed_origins), allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-Access-Token"])


def _step_id(sid: str) -> str:
    sid = (sid or "").upper()
    if not STEP_RE.match(sid):
        raise HTTPException(400, "invalid step id")
    try:
        archive.step(sid)
    except archive.ArchiveError:
        raise HTTPException(404, "unknown step") from None
    return sid


@app.exception_handler(archive.ArchiveError)
async def _archive_err(_, exc):
    return JSONResponse({"detail": str(exc)}, status_code=404)


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    r = db.q1("SELECT provider, model, MAX(created_at) ts, COUNT(*) n FROM investigations GROUP BY provider ORDER BY n DESC LIMIT 1")
    return {"ok": True, "mode": llm.mode(), "documents": db.q1("SELECT COUNT(*) n FROM documents")["n"],
            "investigations": db.q1("SELECT COUNT(*) n FROM investigations")["n"],
            "results": {"provider": r["provider"], "model": r["model"], "computed_at": r["ts"]} if r else None}


@app.get("/api/system")
def system_info():
    return system.summary()


# ---------------------------------------------------------------------------
# Fossil Map
# ---------------------------------------------------------------------------
@app.get("/api/map")
def fossil_map():
    vs = investigate.all_stored()
    procs, totals = [], {"FOSSIL": 0, "FENCE": 0, "ACTIVE": 0, "UNKNOWN": 0, "PENDING": 0}
    fossil_eur = fence_eur = 0
    providers = set()
    for p in archive.processes():
        steps = []
        for i, s in enumerate(p["steps"], start=1):
            v = vs.get(s["id"])
            st = {**s, "process": p["id"], "process_code": p["code"], "process_name": p["name"], "runs_basis": s.get("runs_basis")}
            c = v["cost"] if v else costs.step_cost(st)
            verdict = v["verdict"] if v else "PENDING"
            totals[verdict] += 1
            if verdict == "FOSSIL":
                fossil_eur += c["annual_eur"]
            if verdict == "FENCE":
                fence_eur += c["annual_eur"]
            if v:
                providers.add(f"{v['provider']}:{v['model']}")
            steps.append({"id": s["id"], "seq": i, "name": s.get("name") or s["id"], "instruction": s["instruction"], "verdict": verdict,
                          "strength": v["strength"]["grade"] if v else None, "origin_year": v.get("origin_year") if v else None,
                          "first_seen": v.get("first_seen") if v else None, "annual_cost_eur": c["annual_eur"],
                          "reason": (v.get("reason") or "")[:240] if v else "", "investigated_at": v["created_at"] if v else None})
        procs.append({"id": p["id"], "code": p["code"], "name": p["name"], "short": p.get("short", p["name"]), "kind": p["kind"], "revision": p["revision"],
                      "revision_date": p["revision_date"], "steps": steps})
    return {"plant": archive.mes()["plant"], "processes": procs, "totals": totals, "fossil_annual_eur": fossil_eur,
            "fence_annual_eur": fence_eur, "computed_by": sorted(providers), "mode": llm.mode()}


# ---------------------------------------------------------------------------
# Investigations
# ---------------------------------------------------------------------------
@app.get("/api/steps/{sid}")
def get_step(sid: str):
    sid = _step_id(sid)
    st = archive.step(sid)
    return {"step": st, "verdict": investigate.stored(sid), "cost": costs.step_cost(st),
            "has_recording": (config.settings.recorded_dir / "runs" / f"{sid}.json").is_file()}


@app.get("/api/steps/{sid}/events")
def stored_events(sid: str):
    sid = _step_id(sid)
    return {"events": investigate.stored_events(sid)}


def _ndjson(ev: dict) -> bytes:
    return (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")


@app.post("/api/steps/{sid}/investigate", dependencies=[Depends(require_write)])
async def investigate_live(sid: str):
    sid = _step_id(sid)
    if _live_sem.locked():
        raise HTTPException(429, "Investigations are busy - try again in a moment.")
    q: asyncio.Queue = asyncio.Queue()

    async def emit(ev):
        await q.put(ev)

    async def run():
        async with _live_sem:
            try:
                await investigate.investigate(sid, emit)
            except Exception as e:  # report, never leak internals
                await q.put({"type": "error", "message": f"Investigation failed: {type(e).__name__}"})
            finally:
                await q.put(None)

    task = asyncio.create_task(run())

    async def stream():
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield _ndjson({"type": "heartbeat"})
                    continue
                if ev is None:
                    break
                yield _ndjson(ev)
        finally:
            if not task.done():
                await task

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/steps/{sid}/replay")
async def replay(sid: str, speed: float = 1.0):
    """Replay a recorded AMD run with its original timing (demo mode)."""
    sid = _step_id(sid)
    p = config.settings.recorded_dir / "runs" / f"{sid}.json"
    if not p.is_file():
        raise HTTPException(404, "No recorded AMD run for this step yet.")
    rec = json.loads(p.read_text(encoding="utf-8"))
    speed = min(max(speed, 0.5), 8.0)

    async def stream():
        yield _ndjson({"type": "replay", "recorded_at": rec.get("recorded_at"), "provider": rec.get("provider"),
                       "models": rec.get("models"), "hardware": rec.get("hardware")})
        prev = None
        for ev in rec["events"]:
            if prev is not None:
                await asyncio.sleep(min(2.5, max(0.0, ev.get("t", 0) - prev)) / speed)
            prev = ev.get("t", prev)
            yield _ndjson(ev)

    return StreamingResponse(stream(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
@app.get("/api/docs/{acc}")
def get_doc(acc: str):
    archive.doc_dir(acc)
    d = db.q1("SELECT acc, pages, has_text_layer, title, doc_type, date, lang, refs_json, entities_json, summary, "
              "meta_source, text_source, injection_flag FROM documents WHERE acc=?", (acc,))
    if not d:
        raise HTTPException(404, "document not ingested")
    pages = [{"page": r["page"], "width": r["width"], "height": r["height"], "source": r["source"], "model": r["model"],
              "lines": json.loads(r["lines_json"])} for r in db.q("SELECT * FROM pages WHERE acc=? ORDER BY page", (acc,))]
    out = dict(d)
    out["refs"] = json.loads(out.pop("refs_json") or "{}")
    out["entities"] = json.loads(out.pop("entities_json") or "{}")
    out["pages_data"] = pages
    out["catalog"] = archive.catalog().get(acc, {})
    return out


@app.get("/api/docs/{acc}/pages/{page}")
def get_page(acc: str, page: int):
    p = archive.page_path(acc, page)
    return FileResponse(p, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/archive")
def archive_list():
    rows = db.q("SELECT acc, title, doc_type, date, lang, pages, has_text_layer, injection_flag FROM documents ORDER BY date")
    return {"documents": [dict(r) for r in rows], "synthetic": True}


@app.get("/api/compare")
async def compare(a: str, b: str, request: Request):
    archive.doc_dir(a)
    archive.doc_dir(b)
    try:
        cached = await evolus.compare_docs(a, b, cached_only=True)
    except evolus.EvolusError:
        raise HTTPException(404, "document not ingested") from None
    if cached is not None:
        return {"source": "evolus ai-tools/compare (cached)", "result": cached}
    require_write(request)
    if not config.settings.evolus_configured:
        raise HTTPException(503, "Evolus not configured")
    try:
        return {"source": "evolus ai-tools/compare", "result": await evolus.compare_docs(a, b)}
    except evolus.EvolusError as e:
        raise HTTPException(502, str(e)) from None


# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------
class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    use_evolus_agent: bool = False


@app.post("/api/ask", dependencies=[Depends(require_write)])
async def ask_endpoint(body: AskIn):
    res = await ask.ask(body.question)
    if body.use_evolus_agent and res["type"] == "answer":
        try:
            res["evolus_agent"] = await evolus.agent_chat(body.question)
        except evolus.EvolusError as e:
            res["evolus_agent"] = {"error": str(e)}
    return res


# ---------------------------------------------------------------------------
# Tripwires
# ---------------------------------------------------------------------------
class EventIn(BaseModel):
    type: str = Field(pattern=r"^(supplier_switch|material_substitution|equipment_replacement|regulation_change|step_removal)$")
    process: str | None = Field(default=None, pattern=r"^(ALK|EPX|SOL|TNK|QC)$")
    from_: str = Field(alias="from", min_length=2, max_length=200)
    to: str = Field(min_length=1, max_length=200)

    model_config = {"populate_by_name": True}


@app.get("/api/tripwires")
def tripwire_list():
    recent = [{"id": r["id"], "event": json.loads(r["event_json"]), "alerts": json.loads(r["alerts_json"]),
               "created_at": r["created_at"]} for r in db.q("SELECT * FROM change_events ORDER BY created_at DESC LIMIT 10")]
    return {"registry": tripwires.registry(), "presets": tripwires.PRESETS, "recent": recent}


@app.post("/api/tripwires/simulate", dependencies=[Depends(require_write)])
async def tripwire_simulate(body: EventIn):
    ev = {"type": body.type, "process": body.process, "from": body.from_, "to": body.to}
    return await tripwires.evaluate(ev)


# ---------------------------------------------------------------------------
# Before you change (public REST endpoint for external optimisers)
# ---------------------------------------------------------------------------
class ChangeIn(BaseModel):
    proposal: str = Field(min_length=5, max_length=600)

    @field_validator("proposal")
    @classmethod
    def _strip(cls, v):
        return v.strip()


@app.post("/api/v1/change-check", dependencies=[Depends(require_write)])
async def change_check(body: ChangeIn):
    """Ask CROMO before changing a process. Returns blocked | caution | allowed_with_trial | allowed_with_review | allowed,
    with the fences and evidence involved."""
    return await changecheck.check(body.proposal)


@app.get("/api/change-check/examples")
def change_examples():
    return {"examples": [
        "Remove step SOL-02 (bonding and earthing) to save time",
        "Remove the ammonium chloride addition from AF-12",
        "Shorten the cooling hold before letdown in AF-12 from 30 to 5 minutes",
        "Switch the epoxy resin to a cheaper standard grade resin",
        "Remove the molecular sieve from TL-5",
    ]}


# ---------------------------------------------------------------------------
# Trials (Evolus workflow)
# ---------------------------------------------------------------------------
class TrialIn(BaseModel):
    step_id: str


class DecisionIn(BaseModel):
    approved: bool
    by: str = Field(min_length=2, max_length=60)
    note: str = Field(default="", max_length=300)


@app.get("/api/trials")
def trial_list():
    return {"trials": trials.list_trials(), "workflow_configured": bool(config.settings.evolus_trial_workflow_id
                                                                        and config.settings.evolus_configured)}


@app.post("/api/trials", dependencies=[Depends(require_write)])
async def trial_create(body: TrialIn):
    try:
        return await trials.draft(_step_id(body.step_id))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/trials/{tid}/submit", dependencies=[Depends(require_write)])
async def trial_submit(tid: str):
    try:
        return await trials.submit(tid)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/trials/{tid}/refresh")
async def trial_refresh(tid: str, request: Request):
    rate_limit(request, limit=40, bucket="refresh")
    try:
        return await trials.refresh(tid)
    except KeyError as e:
        raise HTTPException(404, str(e)) from None


@app.post("/api/trials/{tid}/decision", dependencies=[Depends(require_write)])
async def trial_decision(tid: str, body: DecisionIn):
    try:
        return await trials.decide(tid, body.approved, body.by, body.note)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/evolus/webhook")
async def evolus_webhook(request: Request):
    if not token_ok(request.query_params.get("token", "")):
        raise HTTPException(401, "invalid webhook token")
    exe = request.headers.get("X-Workflow-Execution-Id", "")
    body = await request.body()
    if len(body) > 200_000:
        raise HTTPException(413, "payload too large")
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        payload = {"raw": body[:2000].decode("utf-8", "ignore")}
    t = trials.webhook(exe, payload)
    return {"ok": bool(t)}


# ---------------------------------------------------------------------------
# frontend (SPA)
# ---------------------------------------------------------------------------
@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    dist = config.settings.frontend_dist.resolve()
    if path.startswith("api/"):
        raise HTTPException(404)
    target = (dist / path).resolve() if path else dist / "index.html"
    if path and dist in target.parents and target.is_file():
        return FileResponse(target)
    index_html = dist / "index.html"
    if index_html.is_file():
        return FileResponse(index_html, headers={"Cache-Control": "no-cache"})
    return Response("CROMO API is running. Build the frontend (cd frontend && npm run build).", media_type="text/plain")


_started = time.time()
