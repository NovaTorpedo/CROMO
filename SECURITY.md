# Security policy

CROMO is a hackathon prototype. Please report vulnerabilities privately via a GitHub security advisory on this repository rather than a public issue.

## Practices in this repository
- Secrets live only in `.env` (git-ignored). `.env.example` lists names and comments, never values.
- Pre-commit hook (`.githooks/pre-commit`) runs `scripts/secret_scan.py`, which blocks any staged file containing a value from the local `.env`, common credential formats, or an `.env` file; gitleaks runs too when installed. CI runs gitleaks on the full history.
- API keys are used server-side only; the browser never receives them.
- Archive documents are treated as untrusted data: prompts delimit document text, models are told it is data not instructions, outputs are validated against schemas, quotes are verified against the source, and instruction-like text is flagged (see `archive` document with an injected instruction and `backend/tests/test_injection.py`).
- Uploads are size- and type-limited; file access is confined to the archive directory (path traversal checks); rendered text is escaped (no HTML from documents).
- Write/expensive endpoints require an access token when `CROMO_ACCESS_TOKEN` is set, are rate limited, and CORS is restricted to configured origins.
- Containers run as a non-root user with a health check.
