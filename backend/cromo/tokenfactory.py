"""AMD Token Factory account usage (GET /v1/usage): requests, tokens and metered spend for the shared team key.

Used by the benchmark to report what a run consumed, and by check_amd.py to show the remaining daily allowance
before a big run. Returns only secret-free numbers."""

from __future__ import annotations

import httpx

from . import config, llm

KEYS = ("rpm_limit", "daily_cost_limit_usd", "daily_cost_used_usd", "daily_cost_remaining_usd", "daily_reset_at")


def usage() -> dict | None:
    s = config.settings
    role = s.reasoner
    if s.amd_route != "tokenfactory" or not role.base_url or not role.api_key:
        return None
    try:
        with httpx.Client(base_url=role.base_url, headers={"Authorization": f"Bearer {role.api_key}"}, timeout=30,
                          verify=llm._ssl_context()) as c:
            r = c.get("/usage")
        if r.status_code >= 400:
            return None
        j = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    today = j.get("today") or {}
    return {**{k: j.get(k) for k in KEYS},
            "today": {k: today.get(k) for k in ("requests", "errors", "prompt_tokens", "completion_tokens", "reasoning_tokens",
                                                "cached_tokens", "cost")},
            "all_time": {k: (j.get("all_time") or {}).get(k) for k in ("requests", "errors", "total_tokens", "cost")}}


def delta(before: dict | None, after: dict | None) -> dict | None:
    """What happened between two usage() snapshots (all-time counters, so a daily reset in between is harmless)."""
    if not before or not after:
        return None
    a, b = after["all_time"], before["all_time"]
    return {"requests": (a["requests"] or 0) - (b["requests"] or 0), "errors": (a["errors"] or 0) - (b["errors"] or 0),
            "tokens": (a["total_tokens"] or 0) - (b["total_tokens"] or 0),
            "metered_usd": round((a["cost"] or 0) - (b["cost"] or 0), 4)}
