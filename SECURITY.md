# Security policy

CROMO is a hackathon prototype. Please report vulnerabilities privately via a GitHub security advisory on this repository rather than a public issue.

## Practices in this repository
- Secrets live only in `.env` (git-ignored). `.env.example` lists names and comments, never values.
- Pre-commit hook (`.githooks/pre-commit`, enable with `git config core.hooksPath .githooks`) runs `scripts/secret_scan.py`, which blocks any staged file containing a value from the local `.env`, common credential formats, private paths or an `.env` file, and then gitleaks on the staged changes (required; the commit fails if gitleaks is missing). CI runs gitleaks on the full history and fails the build on any finding.
- Security does not rely on the code being secret: everything below holds for an attacker who has read every file, including the prompts.
- API keys are used server-side only; the browser never receives them.
- Archive documents are treated as untrusted data: prompts delimit document text, models are told it is data not instructions, outputs are validated against schemas, quotes are verified against the source, and instruction-like text is flagged (see `archive` document with an injected instruction and `backend/tests/test_injection.py`).
- Request bodies are capped at 256 KB (11 MB only for the optional voice testimony upload, with an audio type allow-list) and every field is length- and pattern-validated. File access is confined to the archive directory (strict accession-number and page validation, path traversal checks). Rendered text is escaped (no HTML from documents); a strict Content-Security-Policy blocks inline and third-party scripts.
- Every endpoint that writes data, calls a model or uses Evolus (investigations, ask, change checks, tripwire simulations, trials, testimony, uncached compares) requires `CROMO_ACCESS_TOKEN` (constant-time comparison). There is no default token: when none is configured these endpoints fail closed for every caller that is not a direct connection from this machine or a private network (requests relayed by a proxy count as remote). The Evolus webhook requires the token and is disabled without one.
- Every API request is rate limited per client (plus stricter limits on write endpoints); request sizes are capped; CORS is off unless origins are configured.
- Errors are generic: unhandled exceptions return "Internal server error." without tracebacks; model and Evolus failures report only a short status (no upstream response text, endpoint paths, workspace ids or environment details), with details kept in the server log. Interactive API docs are off unless `CROMO_API_DOCS=true`.
- Logs never contain keys or tokens (query-string tokens are redacted from access logs) and never full document contents. Evolus call logs replace workspace ids with `:id`; published snapshots and the static demo redact Evolus execution ids.
- The public GitHub Pages demo is static replay data: no keys, no server URLs, and no way to trigger model calls. Production bundles ship without source maps and with a Content-Security-Policy.
- Containers run as a non-root user with a health check.
