"""Access control, rate limiting and security headers."""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from . import config

_hits: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request, *, limit: int = 30, window_s: int = 60, bucket: str = "w") -> None:
    key = f"{bucket}:{client_ip(request)}"
    q = _hits[key]
    now = time.monotonic()
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many requests - please slow down.")
    q.append(now)


def require_write(request: Request) -> None:
    """Gate for endpoints that call models or Evolus (spend credits) or change state."""
    token = config.settings.access_token
    if token:
        given = request.headers.get("X-Access-Token", "")
        if not hmac.compare_digest(given.encode(), token.encode()):
            raise HTTPException(401, "Access token required for this action (demo passcode).")
    rate_limit(request)


MAX_BODY_BYTES = 256 * 1024


class BodyLimit(BaseHTTPMiddleware):
    """Reject oversized request bodies early (all inputs are small JSON documents)."""

    async def dispatch(self, request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            from starlette.responses import JSONResponse

            return JSONResponse({"detail": "Request body too large."}, status_code=413)
        return await call_next(request)


def token_ok(given: str) -> bool:
    token = config.settings.access_token
    return bool(token) and hmac.compare_digest((given or "").encode(), token.encode())


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        return resp
