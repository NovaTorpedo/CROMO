"""Test setup: isolated data dir, offline fixture provider, Evolus disabled (no network, no credits)."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="cromo-test-")
os.environ["CROMO_DATA_DIR"] = _TMP
os.environ["CROMO_PROVIDER"] = "fixture"
os.environ["CROMO_EVOLUS_ENABLED"] = "false"
os.environ["CROMO_ACCESS_TOKEN"] = ""
os.environ["CROMO_METADATA_SOURCE"] = "fixture"
for k in ("CROMO_REASONER_BASE_URL", "CROMO_VISION_BASE_URL", "CROMO_EMBEDDINGS_BASE_URL"):
    os.environ.pop(k, None)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cromo import config  # noqa: E402

config.reload_settings()

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def built():
    """Ingest the whole archive and investigate every step once (offline, ~10 s)."""
    from cromo import ingest, investigate, llm

    async def go():
        await ingest.ingest_all(force=True)
        await investigate.investigate_all(concurrency=8)
        await llm.aclose()

    asyncio.run(go())
    return True
