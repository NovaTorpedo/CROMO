"""Read-only access to the plant archive and plant master data.

Only `archive/` is readable here: documents (page images + optional text layer),
the records catalogue and MES/ERP exports. Path handling is strict to prevent
traversal.
"""

from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path

from . import config

ACC_RE = re.compile(r"^ACC-\d{4}$")


class ArchiveError(ValueError):
    pass


def archive_dir() -> Path:
    return config.settings.archive_dir.resolve()


def _safe(path: Path) -> Path:
    p = path.resolve()
    root = archive_dir()
    if root not in p.parents and p != root:
        raise ArchiveError("path outside archive")
    return p


def doc_dir(acc: str) -> Path:
    if not ACC_RE.match(acc or ""):
        raise ArchiveError("invalid accession number")
    return _safe(archive_dir() / "docs" / acc)


def page_path(acc: str, page: int) -> Path:
    if not isinstance(page, int) or not 1 <= page <= 50:
        raise ArchiveError("invalid page")
    p = _safe(doc_dir(acc) / f"page-{page}.webp")
    if not p.is_file():
        raise ArchiveError("page not found")
    return p


def list_accessions() -> list[str]:
    d = archive_dir() / "docs"
    return sorted(p.name for p in d.iterdir() if p.is_dir() and ACC_RE.match(p.name))


def page_count(acc: str) -> int:
    return len(list(doc_dir(acc).glob("page-*.webp")))


def text_layer(acc: str) -> dict | None:
    p = doc_dir(acc) / "text_layer.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict]:
    with open(archive_dir() / "catalog.csv", encoding="utf-8") as f:
        return {r["accession"]: r for r in csv.DictReader(f)}


@lru_cache(maxsize=1)
def mes() -> dict:
    return json.loads((archive_dir() / "plant" / "mes_recipes_current.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def plant_parameters() -> dict:
    return json.loads((archive_dir() / "plant" / "plant_parameters.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def materials() -> dict[str, dict]:
    out = {}
    with open(archive_dir() / "plant" / "material_master.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["price_eur"] = float(r["price_eur"])
            r["aliases"] = [a for a in r["aliases"].split("|") if a]
            out[r["code"]] = r
    return out


def processes() -> list[dict]:
    return mes()["processes"]


def steps() -> list[dict]:
    out = []
    for p in processes():
        for i, s in enumerate(p["steps"], start=1):
            out.append({**s, "process": p["id"], "process_code": p["code"], "process_name": p["name"], "seq": i})
    return out


def step(step_id: str) -> dict:
    for s in steps():
        if s["id"] == step_id:
            return s
    raise ArchiveError("unknown step")


def process(pid: str) -> dict:
    for p in processes():
        if p["id"] == pid:
            return p
    raise ArchiveError("unknown process")
