# Security policy

CROMO is a hackathon prototype. Please report vulnerabilities privately via a GitHub security advisory on this repository rather than a public issue.

## Practices in this repository
- Secrets live only in `.env` (git-ignored). `.env.example` lists names and comments, never values.
- Pre-commit hook (`.githooks/pre-commit`) runs `scripts/secret_scan.py`, which blocks any staged file containing a value from the local `.env`, common credential formats, or an `.env` file; gitleaks runs too when installed. CI runs gitleaks on the full history.
- API keys are used server-side only; the browser never receives them.
- Archive documents are treated as untrusted data: prompts delimit document text, models are told it is data not instructions, outputs are validated against schemas, quotes are verified against the source, and instruction-like text is flagged (see `archive` document with an injected instruction and `backend/tests/test_injection.py`).
- There are no file-upload endpoints; request bodies are capped at 256 KB and every field is length- and pattern-validated. File access is confined to the archive directory (strict accession-number and page validation, path traversal checks). Rendered text is escaped (no HTML from documents); a strict Content-Security-Policy blocks inline and third-party scripts.
- Write/expensive endpoints (live investigations, Evolus calls, change checks, tripwire simulations, trials) require an access token when `CROMO_ACCESS_TOKEN` is set (constant-time comparison), are rate limited per client, and CORS is restricted to configured origins. The optional Evolus webhook requires the same token.
- Containers run as a non-root user with a health check.
