"""Evolus integration (REST API + OpenAI-compatible agent chat).

Building blocks used by CROMO:
  1. Document extractor  - archive documents (incl. scans) -> structured records   (ingestion metadata)
  2. Workflow            - trial plan -> engineer approval -> status back           (trials)
  3. AI Tool `compare`   - what changed between superseded recipe revisions         (investigation view)
  4. Knowledge library   - archive transcriptions for the Evolus plant agent        (ask)
  5. Agent chat          - Evolus agent running on our AMD vLLM model               (ask)

All results are cached under data/evolus_cache/ so credits are spent once. Calls are rate
limited (60/min workspace limit) and every call is logged with the credits it consumed.
Keys are only used server-side.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path

import httpx

from . import config, db

REST = "https://api.evolus.ai/api/v1"
CHAT = "https://api.evolus.ai/v1"


class EvolusError(RuntimeError):
    pass


def cache_dir() -> Path:
    p = config.settings.data_dir / "evolus_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ----------------------------------------------------------------------------
# cached extractor results (used by ingestion even offline)
# ----------------------------------------------------------------------------
def cached_extraction(acc: str) -> dict | None:
    p = cache_dir() / "extractor" / f"{acc}.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.replace(";", ",").split(",") if x.strip()]
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v)]


def normalise_extraction(d: dict) -> dict:
    """Map the extractor's JSON (our schema, defined in the Evolus workspace) to MetadataOut fields."""
    data = d.get("data", d)
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
