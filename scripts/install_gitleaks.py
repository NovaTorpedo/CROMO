"""Install the pinned gitleaks release into .tools/ (git-ignored) for the pre-commit hook. Free, no admin rights.

  python scripts/install_gitleaks.py

Downloads the official release from GitHub and verifies its SHA-256 against the release's checksums file before
extracting it. Nothing is installed globally.
"""

from __future__ import annotations

import hashlib
import io
import platform
import ssl
import sys
import tarfile
import zipfile
from pathlib import Path

import httpx

VERSION = "8.30.1"  # same version as CI
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".tools"


def _verify():
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


def main() -> None:
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "darwin"}[platform.system()]
    arch = {"AMD64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}[platform.machine()]
    asset = f"gitleaks_{VERSION}_{system}_{arch}." + ("zip" if system == "windows" else "tar.gz")
    base = f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/"
    with httpx.Client(verify=_verify(), follow_redirects=True, timeout=120) as c:
        data = c.get(base + asset).raise_for_status().content
        sums = c.get(base + f"gitleaks_{VERSION}_checksums.txt").raise_for_status().text
    want = next((ln.split()[0] for ln in sums.splitlines() if ln.strip().endswith(asset)), None)
    got = hashlib.sha256(data).hexdigest()
    if want != got:
        sys.exit(f"checksum mismatch for {asset}: refusing to install")
    DEST.mkdir(exist_ok=True)
    exe = "gitleaks.exe" if system == "windows" else "gitleaks"
    if asset.endswith(".zip"):
        zipfile.ZipFile(io.BytesIO(data)).extract(exe, DEST)
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            t.extract(exe, DEST, filter="data")
    (DEST / exe).chmod(0o755)
    print(f"gitleaks {VERSION} installed to {DEST / exe} (sha256 verified)")


if __name__ == "__main__":
    main()
