"""Ask every demo what-if question once against a running CROMO, so the recording shows stored AMD answers at once.

  python scripts/warm_demo.py [http://localhost:8000]

Change checks and tripwire simulations each need one model call; on a busy shared endpoint that can take minutes.
The app stores each live answer (labelled "stored answer from …" in the UI) until a re-investigation changes the
verdicts. Run this after the app is up in live mode and before recording.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from cromo import tripwires  # noqa: E402

CHANGES = [
    "Remove step SOL-02 (bonding and earthing) to save time",
    "Remove the ammonium chloride addition from AF-12",
    "Shorten the cooling hold before letdown in AF-12 from 30 to 5 minutes",
    "Drop the second acetone rinse in SOP-07",
    "Switch the epoxy resin to a cheaper standard grade resin",
    "Reduce the wait after cleaning from 60 to 15 minutes",
]


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    with httpx.Client(base_url=base, timeout=900) as c:
        if c.get("/api/health").json().get("mode") != "amd":
            sys.exit("The app is not in live AMD mode; nothing to warm up.")
        jobs = [("change", p, lambda p=p: c.post("/api/v1/change-check", json={"proposal": p})) for p in CHANGES]
        jobs += [("tripwire", t["label"], lambda t=t: c.post("/api/tripwires/simulate", json=t["event"]))
                 for t in tripwires.PRESETS]
        for kind, label, call in jobs:
            t0 = time.time()
            r = call()
            d = r.json() if r.status_code < 400 else {}
            state = "stored earlier" if d.get("cached_at") else f"computed now in {time.time() - t0:.0f} s"
            print(f"{kind:8s} {r.status_code} {state:28s} {label}", flush=True)


if __name__ == "__main__":
    main()
