"""Take full-resolution screenshots of the running CROMO UI with headless Chrome/Edge.

Used for the README, the cover image and visual QA.

  python scripts/screenshot.py http://localhost:8765/#/ out.png [--size 1600x1000] [--wait 6000] [--light]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def browser() -> str:
    for c in CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("chromium", "google-chrome", "msedge", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    sys.exit("No Chromium-based browser found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--size", default="1600x1000")
    ap.add_argument("--wait", type=int, default=6000, help="virtual time budget in ms")
    ap.add_argument("--light", action="store_true")
    a = ap.parse_args()
    w, h = a.size.split("x")
    out = Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as prof:
        url = a.url
        if a.light:
            url += ("&" if "?" in url else "?") + "theme=light"
        cmd = [browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
               f"--window-size={w},{h}", f"--virtual-time-budget={a.wait}", f"--screenshot={out}",
               "--force-device-scale-factor=1", url]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120, env={**os.environ})
    print(out)


if __name__ == "__main__":
    main()
