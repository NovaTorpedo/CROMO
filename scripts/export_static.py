"""Export the read-only public demo (static files for GitHub Pages - free, no server, no keys).

  python scripts/export_static.py site/data

Writes every GET response the UI needs as JSON, copies page images and recorded AMD runs, and pre-computes the
example interactions (change checks, tripwire presets, ask examples). Build the UI with VITE_STATIC=1 into site/.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from cromo import archive, config, security, tripwires  # noqa: E402

CHANGE_EXAMPLES = [
    "Remove step SOL-02 (bonding and earthing) to save time",
    "Remove the ammonium chloride addition from AF-12",
    "Shorten the cooling hold before letdown in AF-12 from 30 to 5 minutes",
    "Drop the second acetone rinse in SOP-07",
    "Switch the epoxy resin to a cheaper standard grade resin",
    "Reduce the wait after cleaning from 60 to 15 minutes",
]
ASK_EXAMPLES = [
    "Why do we add ammonium chloride to AF-12?",
    "Why do we pre-heat the epoxy drums in the hot box?",
    "Why must the vessel be bonded and earthed before solvent transfer?",
    "Why are TL-5 cans dried in the oven?",
    "What happened with the flash fire at D-2 in 2001?",
    "Which supplier delivered the chromate pigment and when did it stop?",
]


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80]


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "site" / "data").resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    security.rate_limit = lambda *a, **k: None  # local export only

    from cromo.api import app

    def save(rel: str, data):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with TestClient(app) as c:
        def get(path):
            r = c.get(path)
            r.raise_for_status()
            return r.json()

        for name in ("map", "health", "system", "tripwires", "trials", "archive", "change-check/examples"):
            save(f"{name}.json", get(f"/api/{name}"))
        for st in archive.steps():
            save(f"steps/{st['id']}.json", get(f"/api/steps/{st['id']}"))
            save(f"events/{st['id']}.json", get(f"/api/steps/{st['id']}/events"))
        for acc in archive.list_accessions():
            save(f"docs/{acc}.json", get(f"/api/docs/{acc}"))
            for k in range(1, archive.page_count(acc) + 1):
                (out / "pages").mkdir(exist_ok=True)
                shutil.copyfile(archive.page_path(acc, k), out / "pages" / f"{acc}-{k}.webp")
        # cached Evolus comparisons referenced by investigations
        n_cmp = 0
        for st in archive.steps():
            for ev in get(f"/api/steps/{st['id']}/events")["events"]:
                cmp = ev.get("compare")
                if cmp and cmp.get("a"):
                    r = c.get(f"/api/compare?a={cmp['a']}&b={cmp['b']}")
                    if r.status_code == 200:
                        save(f"compare/{cmp['a']}_{cmp['b']}.json", r.json())
                        n_cmp += 1
        # recorded AMD runs (replay)
        runs = config.settings.recorded_dir / "runs"
        if runs.exists():
            for f in runs.glob("*.json"):
                (out / "runs").mkdir(exist_ok=True)
                shutil.copyfile(f, out / "runs" / f.name)
        # pre-computed example interactions
        for p in CHANGE_EXAMPLES:
            save(f"change/{slug(p)}.json", c.post("/api/v1/change-check", json={"proposal": p}).json())
        for pre in tripwires.PRESETS:
            e = pre["event"]
            save(f"tripwires/{slug(e['from'] + '-' + e['to'])}.json", c.post("/api/tripwires/simulate", json=e).json())
        for q in ASK_EXAMPLES:
            save(f"ask/{slug(q)}.json", c.post("/api/ask", json={"question": q}).json())
    print(f"exported static demo data to {out} (compare results: {n_cmp})")


if __name__ == "__main__":
    main()
