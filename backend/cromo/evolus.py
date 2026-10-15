"""Evolus integration (REST API + OpenAI-compatible agent chat).

Building blocks used by CROMO:
  1. Document extractor  - archive documents (incl. scans) -> structured records   (ingestion metadata)
  2. Workflow            - trial plan -> engineer approval -> status back           (trials)
  3. AI Tool `compare`   - what changed between superseded recipe revisions         (investigation view)
  4. Knowledge library   - archive transcriptions for the Evolus plant agent        (ask)
  5. Agent chat          - Evolus agent running on our AMD vLLM model               (ask)

All results are cached under data/evolus_cache/ so credits are spent once. Calls are rate
limited (60/min workspace limit) and every call is logged with the credits it consumed.
Keys are only used server-side and never logged.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import time
from pathlib import Path

import httpx

from . import archive, config, db

REST = "https://api.evolus.ai/api/v1"
CHAT = "https://api.evolus.ai/v1"
MIN_INTERVAL_S = 1.1  # stay under 60 requests/minute


class EvolusError(RuntimeError):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


def cache_dir() -> Path:
    p = config.settings.data_dir / "evolus_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_path(kind: str, key: str) -> Path:
    d = cache_dir() / kind
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def _read_cache(kind: str, key: str):
    p = _cache_path(kind, key)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _write_cache(kind: str, key: str, value) -> None:
    _cache_path(kind, key).write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")


# ----------------------------------------------------------------------------
# cached extractor results (used by ingestion even offline)
# ----------------------------------------------------------------------------
def cached_extraction(acc: str) -> dict | None:
    return _read_cache("extractor", acc)


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.replace(";", ",").split(",") if x.strip()]
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v)]


def normalise_extraction(d: dict) -> dict:
    """Map the extractor's JSON (schema defined in the Evolus workspace) to MetadataOut fields."""
    data = d.get("data", d)
    if isinstance(data, list) and data:
        data = data[0]
    return {
        "doc_type": str(data.get("doc_type") or data.get("document_type") or "other").lower(),
        "date": data.get("date") or data.get("document_date"),
        "title": data.get("title"),
        "language": data.get("language") or "en",
        "reference_numbers": _as_list(data.get("reference_numbers") or data.get("reference_number")),
        "referenced_documents": _as_list(data.get("referenced_documents")),
        "organizations": _as_list(data.get("organizations") or data.get("suppliers")),
        "materials": _as_list(data.get("materials")),
        "equipment": _as_list(data.get("equipment")),
        "products": _as_list(data.get("products")),
        "regulations": _as_list(data.get("regulations")),
        "people": _as_list(data.get("people")),
        "summary": str(data.get("summary") or "")[:400],
        "suspicious_instructions": bool(data.get("suspicious_instructions", False)),
    }


# ----------------------------------------------------------------------------
# client
# ----------------------------------------------------------------------------
_last_call = 0.0
_lock = asyncio.Lock()


def _ssl():
    try:
        import ssl

        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # pragma: no cover
        return True


def _headers() -> dict:
    s = config.settings
    if not s.evolus_configured:
        raise EvolusError("Evolus is not configured (EVOLUS_API_KEY / EVOLUS_APPLICATION_ID)")
    return {"X-ApiKey": s.evolus_api_key, "X-Application-Id": s.evolus_application_id}


def _log(endpoint: str, status: int, credits: float | None, note: str = "") -> None:
    db.ex("INSERT INTO evolus_calls(endpoint, status, credits, ts, note) VALUES(?,?,?,?,?)",
          (endpoint, status, credits, time.time(), note[:200]))


async def _request(method: str, path: str, *, base: str = REST, **kw) -> httpx.Response:
    global _last_call
    headers = {"Accept-Language": "en-US,en;q=0.9", **_headers(), **kw.pop("headers", {})}
    endpoint = path.split("?")[0]
    async with _lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()
    for attempt in range(3):
        async with httpx.AsyncClient(verify=_ssl(), timeout=httpx.Timeout(180, connect=20)) as c:
            try:
                r = await c.request(method, base + path, headers=headers, **kw)
            except httpx.HTTPError as e:
                _log(endpoint, 0, None, type(e).__name__)
                if attempt == 2:
                    raise EvolusError(f"Evolus unreachable: {type(e).__name__}") from e
                await asyncio.sleep(2 * (attempt + 1))
                continue
        if r.status_code == 429:
            _log(endpoint, 429, None, "rate limited")
            await asyncio.sleep(5 * (attempt + 1))
            continue
        credits = None
        if r.headers.get("X-Credits-Consumed"):
            try:
                credits = float(r.headers["X-Credits-Consumed"])
            except ValueError:
                pass
        if credits is None and r.headers.get("content-type", "").startswith("application/json"):
            try:
                j = r.json()
                if isinstance(j, dict) and "creditsConsumed" in j:
                    credits = float(j["creditsConsumed"])
            except (ValueError, TypeError):
                pass
        _log(endpoint, r.status_code, credits)
        if r.status_code == 402:
            raise EvolusError("Evolus platform credits exhausted (402)", 402)
        if r.status_code >= 400:
            detail = r.text[:300]
            raise EvolusError(f"Evolus {method} {endpoint} -> HTTP {r.status_code}: {detail}", r.status_code)
        return r
    raise EvolusError("Evolus rate limit: retries exhausted", 429)


# ----------------------------------------------------------------------------
# AI Tools (compare, summarize, ...)
# ----------------------------------------------------------------------------
async def ai_tool(tool: str, text: str, secondary: str | None = None, options: dict | None = None, *,
                  cached_only: bool = False) -> dict | None:
    key = hashlib.sha256(json.dumps([tool, text, secondary, options], sort_keys=True).encode()).hexdigest()[:24]
    hit = _read_cache("ai_tools", key)
    if hit is not None or cached_only:
        return hit
    body = {"text": text[:110000]}
    if secondary is not None:
        body["secondaryText"] = secondary[:110000]
    if options:
        body["options"] = options
    r = await _request("POST", f"/ai-tools/{tool}/run", json=body)
    out = r.json()
    out["_cached_at"] = time.time()
    _write_cache("ai_tools", key, out)
    return out


def _doc_text(acc: str) -> str:
    r = db.q1("SELECT text FROM documents WHERE acc=?", (acc,))
    if not r:
        raise EvolusError("document not ingested")
    return r["text"]


async def compare_docs(acc_a: str, acc_b: str, *, cached_only: bool = False) -> dict | None:
    return await ai_tool("compare", _doc_text(acc_a), _doc_text(acc_b), cached_only=cached_only)


# ----------------------------------------------------------------------------
# Document extractor
# ----------------------------------------------------------------------------
def doc_pdf(acc: str) -> bytes:
    """Image PDF of the archive document (what a scanner would produce)."""
    from PIL import Image

    imgs = [Image.open(archive.page_path(acc, k)).convert("RGB") for k in range(1, archive.page_count(acc) + 1)]
    buf = io.BytesIO()
    imgs[0].save(buf, format="PDF", save_all=True, append_images=imgs[1:], resolution=120)
    return buf.getvalue()


async def extract(acc: str, *, force: bool = False) -> dict:
    s = config.settings
    if not force:
        hit = cached_extraction(acc)
        if hit is not None:
            return hit
    if not (s.evolus_extractor_agent_id and s.evolus_extractor_id):
        raise EvolusError("Evolus extractor ids not configured")
    files = {"file": (f"{acc}.pdf", doc_pdf(acc), "application/pdf")}
    r = await _request("POST", f"/agents/{s.evolus_extractor_agent_id}/json/{s.evolus_extractor_id}/ask-file?useWebhook=false",
                       files=files)
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text}
    out = {"acc": acc, "data": data, "execution_id": r.headers.get("X-AskFile-Execution-Id"),
           "credits": r.headers.get("X-Credits-Consumed"), "_cached_at": time.time()}
    _write_cache("extractor", acc, out)
    return out


# ----------------------------------------------------------------------------
# Knowledge library
# ----------------------------------------------------------------------------
async def library_upload(acc: str) -> dict:
    s = config.settings
    hit = _read_cache("library", acc)
    if hit is not None:
        return hit
    if not s.evolus_library_id:
        raise EvolusError("Evolus library id not configured")
    r = db.q1("SELECT text, title, doc_type, date, lang FROM documents WHERE acc=?", (acc,))
    if not r:
        raise EvolusError("document not ingested")
    md = (f"# {acc} - {r['title'] or r['doc_type'] or 'document'}\n\nAccession: {acc}  \nType: {r['doc_type']}  \n"
          f"Date: {r['date']}  \nSource: Valdorso synthetic archive (fictional)\n\n{r['text']}\n")
    lang = "it" if (r["lang"] or "en") == "it" else "en"
    resp = await _request("POST", f"/memories/{s.evolus_library_id}/documents?language={lang}",
                          files={"file": (f"{acc}.md", md.encode("utf-8"), "text/markdown")})
    body = resp.json() if resp.content else {}
    # keep only what CROMO needs; workspace and library ids are not stored in the repo
    out = {"acc": acc, "document_id": body.get("id") or body.get("documentId"), "indexed": True, "_cached_at": time.time()}
    _write_cache("library", acc, out)
    return out


# ----------------------------------------------------------------------------
# Workflows
# ----------------------------------------------------------------------------
async def run_workflow(workflow_id: str, text: str, *, parameters: dict | None = None,
                       files: dict | None = None, callback_url: str | None = None) -> dict:
    # multipart/form-data: text fields are sent as parts without a filename
    parts: list = [("input", (None, text))]
    if parameters:
        parts.append(("parameters", (None, json.dumps(parameters))))
    if callback_url:
        parts.append(("callbackUrl", (None, callback_url)))
    for name, f in (files or {}).items():
        parts.append(("file", f) if name.startswith("file") else (name, f))
    r = await _request("POST", f"/workflows/{workflow_id}/execute", files=parts)
    j = r.json() if r.content else {}
    j["executionId"] = j.get("executionId") or r.headers.get("X-Workflow-Execution-Id")
    return j


async def get_execution(workflow_id: str, execution_id: str) -> dict:
    r = await _request("GET", f"/workflows/{workflow_id}/executions/{execution_id}")
    return r.json()


async def list_workflows() -> list:
    return (await _request("GET", "/workflows")).json()


# ----------------------------------------------------------------------------
# Agent chat (OpenAI-compatible; the agent runs on our AMD vLLM model)
# ----------------------------------------------------------------------------
async def agent_chat(question: str, conversation_id: str | None = None) -> dict:
    s = config.settings
    if not s.evolus_agent_model:
        raise EvolusError("Evolus agent not configured (EVOLUS_AGENT_MODEL)")
    headers = {"Authorization": f"Bearer {s.evolus_api_key}", "Content-Type": "application/json"}
    if conversation_id:
        headers["X-Conversation-Id"] = conversation_id
    body = {"model": s.evolus_agent_model, "messages": [{"role": "user", "content": question[:4000]}]}
    t0 = time.perf_counter()
    async with httpx.AsyncClient(verify=_ssl(), timeout=httpx.Timeout(180, connect=20)) as c:
        r = await c.post(CHAT + "/chat/completions", headers=headers, json=body)
    _log("/v1/chat/completions", r.status_code, None)
    if r.status_code >= 400:
        raise EvolusError(f"Evolus agent HTTP {r.status_code}: {r.text[:200]}", r.status_code)
    j = r.json()
    return {"answer": j["choices"][0]["message"].get("content", ""), "conversation_id": r.headers.get("X-Conversation-Id"),
            "latency_ms": round((time.perf_counter() - t0) * 1000), "model": s.evolus_agent_model}


# ----------------------------------------------------------------------------
# usage summary for the System page
# ----------------------------------------------------------------------------
def usage() -> dict:
    rows = db.q("SELECT endpoint, COUNT(*) n, SUM(COALESCE(credits,0)) credits, "
                "SUM(CASE WHEN status BETWEEN 200 AND 299 THEN 1 ELSE 0 END) ok FROM evolus_calls GROUP BY endpoint")
    calls = [dict(r) for r in rows]
    cache_counts = {k: len(list((cache_dir() / k).glob("*.json"))) if (cache_dir() / k).exists() else 0
                    for k in ("extractor", "ai_tools", "library")}
    return {"calls": calls, "credits_logged": round(sum(c["credits"] or 0 for c in calls), 2), "cached": cache_counts,
            "budget": 50000}
