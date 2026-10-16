"""Wait until the configured reasoner endpoint answers a tiny chat request, then exit 0.

  python scripts/wait_for_endpoint.py [--every 180] [--max-hours 6]

Used before resuming a long run after an outage of the shared AMD Token Factory (HTTP 500/503 "no available workers"):
one 5-token request every few minutes, nothing else. Never prints keys.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402

from cromo import config, llm  # noqa: E402


def probe(role: config.RoleConfig) -> tuple[bool, str]:
    try:
        with httpx.Client(base_url=role.base_url, headers={"Authorization": f"Bearer {role.api_key}"} if role.api_key else {},
                          timeout=120, verify=llm._ssl_context()) as c:
            r = c.post("/chat/completions", json={"model": role.model, "max_tokens": 5, "temperature": 0,
                                                  "messages": [{"role": "user", "content": "Reply with the word ok"}]})
        if r.status_code == 200 and (r.json()["choices"][0]["message"].get("content") or "").strip():
            return True, "ok"
        return False, f"HTTP {r.status_code}: {llm._error_text(r)[:120]}"
    except (httpx.HTTPError, ValueError, KeyError) as e:
        return False, type(e).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=180, help="seconds between probes")
    ap.add_argument("--max-hours", type=float, default=6)
    a = ap.parse_args()
    role = config.settings.reasoner
    if not role.configured:
        sys.exit("No reasoner endpoint configured.")
    deadline = time.time() + a.max_hours * 3600
    while time.time() < deadline:
        ok, why = probe(role)
        print(time.strftime("%H:%M:%S"), role.model, "UP" if ok else f"down ({why})", flush=True)
        if ok:
            return
        time.sleep(a.every)
    sys.exit("endpoint still down after the waiting time")


if __name__ == "__main__":
    main()
