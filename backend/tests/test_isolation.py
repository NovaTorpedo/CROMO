"""Ground-truth isolation: the product must never read eval/ or generator/ (no leakage into verdicts)."""

import asyncio
import builtins
import io
import re
from pathlib import Path

from conftest import ROOT

FORBIDDEN = ("ground_truth", "eval/", "eval\\", "generator", "scenario_truth", "scenario_docs")


def test_product_source_never_references_truth():
    for py in (ROOT / "backend" / "cromo").glob("*.py"):
        text = py.read_text(encoding="utf-8")
        for bad in FORBIDDEN:
            assert bad not in text, f"{py.name} references {bad!r}"


def test_frontend_never_fetches_truth():
    for f in (ROOT / "frontend" / "src").rglob("*.ts*"):
        assert not re.search(r"(get|post|fetch)[^\n]*ground_truth", f.read_text(encoding="utf-8"))


def test_runtime_file_access_never_touches_truth(built, monkeypatch):
    """Audit every file opened while ingesting and investigating."""
    from cromo import ingest, investigate, llm

    opened: list[str] = []
    real_open = builtins.open
    real_io_open = io.open
    real_read_text = Path.read_text
    real_read_bytes = Path.read_bytes

    def rec(p):
        opened.append(str(p).replace("\\", "/"))

    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (rec(f), real_open(f, *a, **k))[1])
    monkeypatch.setattr(io, "open", lambda f, *a, **k: (rec(f), real_io_open(f, *a, **k))[1])
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (rec(self), real_read_text(self, *a, **k))[1])
    monkeypatch.setattr(Path, "read_bytes", lambda self, *a, **k: (rec(self), real_read_bytes(self, *a, **k))[1])

    async def go():
        await ingest.ingest_doc("ACC-0001")
        await ingest.embed_all()
        await investigate.investigate("ALK-04", store=False)
        await investigate.investigate("SOL-02", store=False)
        await llm.aclose()

    asyncio.run(go())
    assert opened, "audit hook saw no file access"
    root = str(ROOT).replace("\\", "/")
    for p in opened:
        rel = p.replace(root, "")
        assert not re.search(r"(^|/)(eval|generator)/", rel), f"pipeline opened {p}"
