"""Local secret and privacy scanner used by the pre-commit hook and CI (complements gitleaks).

1. Blocks any file that contains a literal value from the local .env: keys, tokens and passwords, but also workspace
   ids (Evolus application / workflow / library / extractor / agent) and private server URLs. Checked in every file,
   binaries included - the strongest guarantee that real keys and infrastructure details never reach git.
2. Blocks common credential formats and suspicious key=value assignments.
3. Blocks private details: home-directory paths and public IP addresses (documentation ranges are allowed).
Never prints secret values, only file names and rule names.

Usage: python scripts/secret_scan.py [--staged | --all]
"""
from __future__ import annotations

import ipaddress
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_SUFFIX = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".ttf", ".woff", ".woff2", ".ico", ".pdf", ".mp4", ".db"}
SKIP_DIRS = ("archive/docs/", "generator/fonts/", "node_modules/", ".venv/")
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "openai-style-key": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "hf-token": re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "bearer-literal": re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]{24,}"),
    "url-with-credentials": re.compile(r"https?://[^/\s:@<>]+:[^/\s@<>]+@"),
    # a quoted literal assigned to a secret-looking name (code references like settings.api_key are fine)
    "assigned-secret": re.compile(
        r"(?i)\b[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)\s*[=:]\s*['\"](?!your|changeme|example|xxx)[A-Za-z0-9_\-\.+/=]{20,}['\"]"),
    "env-style-secret": re.compile(
        r"(?m)^\s*[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)=(?!\$|<|your|changeme|example)[A-Za-z0-9_\-\.+/=]{20,}\s*$"),
    "home-directory-path": re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+(?!<|Public\b)[A-Za-z0-9._-]+|(?<![\w.])/(?:home|Users)/(?!<|runner\b|user\b|you\b)[a-z0-9._-]+/"),
}
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
# documentation, loopback, unspecified and private ranges are fine in docs and code
IP_OK = [ipaddress.ip_network(n) for n in ("0.0.0.0/8", "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                                           "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
IP_SKIP_DIRS = ("fixtures/", "eval/", "data/")  # synthetic transcriptions and recorded numbers contain dotted numbers
# .env variables whose values are private even though they are not keys
PRIVATE_NAME = re.compile(r"KEY|SECRET|TOKEN|PASSWORD|PASSCODE|_ID$|_IDS$|BASE_URL|AGENT_MODEL|APPLICATION")


def env_values() -> list[str]:
    vals = []
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if len(v) >= 8 and PRIVATE_NAME.search(name.strip().upper()) and not re.search(r"localhost|127\.0\.0\.1", v):
                    vals.append(v)
    return vals


def files(mode: str) -> list[str]:
    if mode == "--staged":
        out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    else:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f]


def public_ips(text: str) -> bool:
    for m in IPV4.findall(text):
        try:
            ip = ipaddress.ip_address(m)
        except ValueError:
            continue
        if not any(ip in n for n in IP_OK):
            return True
    return False


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--staged"
    secrets = [s.encode() for s in env_values()]
    problems = []
    for f in files(mode):
        norm = f.replace("\\", "/")
        if norm in (".env",) or (norm.startswith(".env.") and norm != ".env.example"):
            problems.append((f, "env-file-committed"))
            continue
        p = ROOT / f
        if not p.is_file():
            continue
        raw = p.read_bytes()
        if any(s in raw for s in secrets):  # every file, binaries included
            problems.append((f, "value-from-local-.env"))
        if Path(f).suffix.lower() in SKIP_SUFFIX or norm.startswith(SKIP_DIRS) or norm == "scripts/secret_scan.py":
            continue
        text = raw.decode("utf-8", errors="ignore")
        for rule, rx in PATTERNS.items():
            if rx.search(text):
                problems.append((f, rule))
        if not norm.startswith(IP_SKIP_DIRS) and not norm.endswith("package-lock.json") and public_ips(text):
            problems.append((f, "public-ip-address"))
    if problems:
        print("SECRET SCAN FAILED - remove these before committing:")
        for f, rule in sorted(set(problems)):
            print(f"  {f}: {rule}")
        return 1
    print(f"secret scan ok ({mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
