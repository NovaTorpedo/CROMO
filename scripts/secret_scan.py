"""Local secret scanner used by the pre-commit hook and CI (complements gitleaks).

1. Blocks any staged file that contains a literal value from the local .env
   (the strongest guarantee that real keys never reach git).
2. Blocks common credential formats and suspicious key=value assignments.
Never prints secret values, only file names and rule names.

Usage: python scripts/secret_scan.py [--staged | --all]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_SUFFIX = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".ttf", ".woff", ".woff2", ".ico", ".pdf", ".mp4"}
SKIP_DIRS = ("archive/docs/", "generator/fonts/", "node_modules/", ".venv/")
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "openai-style-key": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "hf-token": re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "bearer-literal": re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]{24,}"),
    "assigned-secret": re.compile(
        r"(?i)\b[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)\s*[=:]\s*['\"]?(?!\$|<|\{|your|changeme|example|xxx|none|null|\"\")[A-Za-z0-9_\-\.]{20,}"),
}


def env_values() -> list[str]:
    vals = []
    for name in (".env",):
        p = ROOT / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if len(v) >= 12:
                    vals.append(v)
    return vals


def files(mode: str) -> list[str]:
    if mode == "--staged":
        out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    else:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--staged"
    secrets = env_values()
    problems = []
    for f in files(mode):
        norm = f.replace("\\", "/")
        if norm in (".env",) or (norm.startswith(".env.") and norm != ".env.example"):
            problems.append((f, "env-file-committed"))
            continue
        if Path(f).suffix.lower() in SKIP_SUFFIX or norm.startswith(SKIP_DIRS):
            continue
        p = ROOT / f
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for s in secrets:
            if s in text:
                problems.append((f, "value-from-local-.env"))
        for rule, rx in PATTERNS.items():
            if rx.search(text):
                problems.append((f, rule))
    if problems:
        print("SECRET SCAN FAILED - remove these before committing:")
        for f, rule in sorted(set(problems)):
            print(f"  {f}: {rule}")
        return 1
    print(f"secret scan ok ({mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
