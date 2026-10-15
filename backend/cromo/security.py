"""Access control, rate limiting and security headers."""

from __future__ import annotations

import hmac
import ipaddress
import logging
import re
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


_PROXY_HEADERS = ("x-forwarded-for", "x-real-ip", "forwarded")


def is_local_client(request: Request) -> bool:
    """A direct connection from this machine or a private network (e.g. the Docker bridge), not relayed by a proxy."""
    if any(h in request.headers for h in _PROXY_HEADERS):
        return False
    try:
        ip = ipaddress.ip_address(client_ip(request))
    except ValueError:
        return False
    return ip.is_loopback or any(ip in n for n in _LOCAL_NETS)


# RFC 1918 + IPv6 unique-local: a developer machine, LAN or Docker bridge (ipaddress.is_private is broader than that)
_LOCAL_NETS = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")]


def require_write(request: Request) -> None:
    """Gate for endpoints that call models or Evolus (spend credits) or change state.

    With CROMO_ACCESS_TOKEN set, every caller must send it (X-Access-Token, constant-time compare). Without a token the
    gate fails closed: only direct local / private-network callers (a developer's own machine) may use these actions.
    There is no default token."""
    token = config.settings.access_token
    if token:
        given = request.headers.get("X-Access-Token", "")
        if not hmac.compare_digest(given.encode(), token.encode()):
            raise HTTPException(401, "Access token required for this action (demo passcode).")
    elif not is_local_client(request):
        raise HTTPException(403, "This action is disabled on this deployment.")
    rate_limit(request)


class GlobalRateLimit(BaseHTTPMiddleware):
    """Per-client ceiling on every API request (reads included); write endpoints have stricter limits on top."""

    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/api/"):
            try:
                rate_limit(request, limit=GLOBAL_LIMIT_PER_MIN, window_s=60, bucket="all")
            except HTTPException as e:
                from starlette.responses import JSONResponse

                return JSONResponse({"detail": e.detail}, status_code=e.status_code)
        return await call_next(request)


GLOBAL_LIMIT_PER_MIN = 600


class RedactQueryTokens(logging.Filter):
    """Access logs record full URLs; the Evolus webhook carries its token in the query string. Redact it."""

    _rx = re.compile(r"(?i)([?&](?:token|key|api_key|apikey|access_token)=)[^&\s]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(self._rx.sub(r"\1[redacted]", a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.msg, str):
            record.msg = self._rx.sub(r"\1[redacted]", record.msg)
        return True


logging.getLogger("uvicorn.access").addFilter(RedactQueryTokens())

MAX_BODY_BYTES = 256 * 1024


class BodyLimit(BaseHTTPMiddleware):
    """Reject oversized request bodies early (all inputs are small JSON documents)."""

    async def dispatch(self, request, call_next):
        cl = request.headers.get("content-length")
        limit = 11 * 1024 * 1024 if request.url.path.endswith("/testimony") else MAX_BODY_BYTES
        if cl and cl.isdigit() and int(cl) > limit:
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
