"""Check that every configured AMD endpoint (and Evolus) works before switching CROMO to live mode.

  python scripts/check_amd.py            # all roles + Evolus
  python scripts/check_amd.py --role reasoner

Exit code 0 = everything needed works. Every failure prints what to fix.
Never prints keys.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402

from cromo import config  # noqa: E402

OK, FAIL, WARN = "\033[32mOK\033[0m", "\033[31mFAIL\033[0m", "\033[33mWARN\033[0m"
results: list[tuple[str, str, str]] = []


def ssl():
    try:
        import ssl as _ssl

        import truststore

        return truststore.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return True


def report(name: str, status: str, detail: str = ""):
    results.append((name, status, detail))
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))


def client(role: config.RoleConfig) -> httpx.Client:
    h = {"Content-Type": "application/json"}
    if role.api_key:
        h["Authorization"] = f"Bearer {role.api_key}"
    return httpx.Client(base_url=role.base_url, headers=h, timeout=180, verify=ssl())


def check_models(role: config.RoleConfig, c: httpx.Client) -> bool:
    env = f"CROMO_{role.role.upper()}"
    try:
        t0 = time.perf_counter()
        r = c.get("/models")
        ms = (time.perf_counter() - t0) * 1000
    except httpx.HTTPError as e:
        report(f"{role.role}: reach endpoint", FAIL,
               f"{type(e).__name__}. Check {env}_BASE_URL (must end with /v1), that the server is running "
               "(deploy/amd/serve_vllm.sh status) and that the port is open (deploy/amd/firewall.sh).")
        return False
    if r.status_code == 401:
        report(f"{role.role}: authentication", FAIL, f"key rejected. {env}_API_KEY must equal the --api-key / VLLM_API_KEY of the server.")
        return False
    if r.status_code >= 400:
        report(f"{role.role}: list models", FAIL, f"HTTP {r.status_code}: {r.text[:160]}")
        return False
    ids = [m.get("id") for m in r.json().get("data", [])]
    report(f"{role.role}: endpoint + auth", OK, f"{ms:.0f} ms, serves {', '.join(ids[:4])}")
    if role.model not in ids:
        report(f"{role.role}: model name", FAIL, f"'{role.model}' is not served here. Set {env}_MODEL to one of: {ids}")
        return False
    return True


def check_reasoner(role, c):
    t0 = time.perf_counter()
    r = c.post("/chat/completions", json={"model": role.model, "max_tokens": 20, "temperature": 0,
                                          "messages": [{"role": "user", "content": "Reply with the single word: ready"}]})
    ms = (time.perf_counter() - t0) * 1000
    if r.status_code >= 400:
        report("reasoner: chat completion", FAIL, f"HTTP {r.status_code}: {r.text[:200]}")
        return
    txt = r.json()["choices"][0]["message"].get("content") or ""
    report("reasoner: chat completion", OK, f"{ms:.0f} ms, said {txt.strip()[:40]!r}")
    # JSON / structured output
    schema = {"type": "object", "properties": {"verdict": {"type": "string", "enum": ["FOSSIL", "FENCE"]}}, "required": ["verdict"]}
    for mode, rf in (("json_schema", {"type": "json_schema", "json_schema": {"name": "t", "schema": schema}}),
                     ("json_object", {"type": "json_object"})):
        r = c.post("/chat/completions", json={"model": role.model, "max_tokens": 40, "temperature": 0, "response_format": rf,
                                              "messages": [{"role": "user", "content": 'Return JSON {"verdict": "FENCE"}'}]})
        if r.status_code < 400:
            try:
                json.loads(r.json()["choices"][0]["message"]["content"])
                report(f"reasoner: structured output ({mode})", OK, f"set CROMO_STRUCTURED_OUTPUT={mode}")
                break
            except (ValueError, KeyError, TypeError):
                pass
        report(f"reasoner: structured output ({mode})", WARN, "not supported; CROMO falls back to prompt-only JSON")
    # tool calling (required by Evolus agents)
    tools = [{"type": "function", "function": {"name": "get_step_status", "description": "Look up a recipe step",
                                               "parameters": {"type": "object", "properties": {"step_id": {"type": "string"}},
                                                              "required": ["step_id"]}}}]
    t0 = time.perf_counter()
    r = c.post("/chat/completions", json={"model": role.model, "max_tokens": 200, "temperature": 0, "tools": tools,
                                          "tool_choice": "auto",
                                          "messages": [{"role": "user", "content": "What is the status of step ALK-04? Use the tool."}]})
    ms = (time.perf_counter() - t0) * 1000
    calls = (r.json()["choices"][0]["message"].get("tool_calls") or []) if r.status_code < 400 else []
    if calls:
        report("reasoner: tool calling", OK, f"{ms:.0f} ms, called {calls[0]['function']['name']}")
    else:
        report("reasoner: tool calling", FAIL if r.status_code >= 400 else WARN,
               "no tool call. Evolus agents need it: start vLLM with --enable-auto-tool-choice --tool-call-parser hermes "
               "(Qwen family). " + (r.text[:150] if r.status_code >= 400 else ""))


def scanned_page() -> tuple[str, bytes, str] | None:
    import csv

    with open(ROOT / "archive" / "catalog.csv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["text_layer"] == "no"]
    if not rows:
        return None
    acc = rows[0]["accession"]
    data = (ROOT / "archive" / "docs" / acc / "page-1.webp").read_bytes()
    import hashlib

    fx = ROOT / "fixtures" / "vision" / f"{hashlib.sha256(data).hexdigest()}.json"
    ref = " ".join(ln["text"] for ln in json.loads(fx.read_text(encoding="utf-8"))["lines"]) if fx.exists() else ""
    return acc, data, ref


def check_vision(role, c):
    sp = scanned_page()
    if not sp:
        report("vision: test page", WARN, "no scanned page found in archive")
        return
    acc, data, ref = sp
    t0 = time.perf_counter()
    r = c.post("/chat/completions", json={"model": role.model, "max_tokens": 1200, "temperature": 0, "messages": [{
        "role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/webp;base64," + base64.b64encode(data).decode()}},
            {"type": "text", "text": "Transcribe all text on this scanned page exactly, line by line."}]}]})
    ms = (time.perf_counter() - t0) * 1000
    if r.status_code >= 400:
        report("vision: read a scanned page", FAIL,
               f"HTTP {r.status_code}: {r.text[:200]}. Is CROMO_VISION_MODEL a vision-language model (e.g. Qwen2.5-VL)?")
        return
    out = r.json()["choices"][0]["message"].get("content") or ""
    import difflib

    sim = difflib.SequenceMatcher(None, " ".join(out.split()).lower(), " ".join(ref.split()).lower()).ratio() if ref else None
    report("vision: read a scanned page", OK if (sim is None or sim > 0.6) else WARN,
           f"{acc}, {ms:.0f} ms" + (f", character similarity to reference {sim:.0%}" if sim is not None else ""))


def check_embeddings(role, c):
    t0 = time.perf_counter()
    r = c.post("/embeddings", json={"model": role.model, "input": [
        "ammonium chloride added to the alkyd enamel", "cloruro d'ammonio aggiunto allo smalto", "forklift battery replaced"]})
    ms = (time.perf_counter() - t0) * 1000
    if r.status_code >= 400:
        report("embeddings: embed", FAIL, f"HTTP {r.status_code}: {r.text[:200]}. Serve an embedding model (e.g. BAAI/bge-m3).")
        return
    import numpy as np

    v = np.array([d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])], dtype=float)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    same, diff = float(v[0] @ v[1]), float(v[0] @ v[2])
    report("embeddings: embed", OK if same > diff else WARN,
           f"{ms:.0f} ms, dim {v.shape[1]}, EN/IT same-meaning similarity {same:.2f} vs unrelated {diff:.2f}")


def check_evolus():
    s = config.settings
    if not s.evolus_configured:
        report("evolus: configured", WARN, "EVOLUS_API_KEY / EVOLUS_APPLICATION_ID not set")
        return
    h = {"X-ApiKey": s.evolus_api_key, "X-Application-Id": s.evolus_application_id}
    with httpx.Client(base_url="https://api.evolus.ai/api/v1", headers=h, timeout=30, verify=ssl()) as c:
        for path, what in (("/ai-tools", "AI Tools"), ("/workflows", "workflows"), ("/agents", "agents"), ("/memories", "libraries")):
            try:
                r = c.get(path)
            except httpx.HTTPError as e:
                report(f"evolus: {what}", FAIL, type(e).__name__)
                continue
            if r.status_code < 300:
                n = len(r.json()) if isinstance(r.json(), list) else "?"
                report(f"evolus: {what}", OK, f"{n} item(s)")
            else:
                report(f"evolus: {what}", WARN, f"HTTP {r.status_code} - the API key may lack this permission (recreate it with all permissions)")
    for name, val in (("trial workflow id", s.evolus_trial_workflow_id), ("extractor ids", s.evolus_extractor_id),
                      ("library id", s.evolus_library_id), ("agent model", s.evolus_agent_model)):
        report(f"evolus: {name}", OK if val else WARN, "set" if val else "not set (see docs/EVOLUS_SETUP.md)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["reasoner", "vision", "embeddings", "evolus"])
    a = ap.parse_args()
    s = config.settings
    print(f"CROMO provider={s.provider} route={s.amd_route}")
    if s.provider != "amd":
        report("CROMO_PROVIDER", WARN, "is not 'amd' - the app will stay in offline fixture mode until you set CROMO_PROVIDER=amd")
    checks = {"reasoner": check_reasoner, "vision": check_vision, "embeddings": check_embeddings}
    for name, fn in checks.items():
        if a.role and a.role != name:
            continue
        role = getattr(s, name)
        print(f"\n{name.upper()}  model={role.model or '-'}")
        if not role.configured:
            report(f"{name}: configured", FAIL if name == "reasoner" else WARN,
                   f"set CROMO_{name.upper()}_BASE_URL and CROMO_{name.upper()}_MODEL"
                   + ("" if name == "reasoner" else " (falls back to the reasoner endpoint if it serves this role)"))
            continue
        with client(role) as c:
            if check_models(role, c):
                try:
                    fn(role, c)
                except httpx.HTTPError as e:
                    report(f"{name}: request", FAIL, type(e).__name__)
    if not a.role or a.role == "evolus":
        print("\nEVOLUS")
        check_evolus()
    fails = [r for r in results if r[1] == FAIL]
    print("\n" + ("ALL REQUIRED CHECKS PASSED" if not fails else f"{len(fails)} CHECK(S) FAILED - fix the items marked FAIL above"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
