"""Production hardening: security headers, per-client rate limits on costly endpoints, refuse default secrets in prod."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings

# (method, path prefix) -> (max requests, window seconds) per client. In-memory: per instance (Cloud Run runs a single instance, see docs/deploy.md).
LIMITS: dict[tuple[str, str], tuple[int, int]] = {
    ("POST", "/advisor/sessions"): (30, 60),     # session creation
    ("POST", "/advisor/sessions/"): (120, 60),   # chat messages (LLM cost; shared NATs need headroom, plus 80 messages per session)
    ("POST", "/kyc/"): (60, 60),                 # uploads and lookups
    ("POST", "/checkout/otp"): (10, 60),
    ("POST", "/checkout"): (20, 60),
    ("POST", "/consents"): (30, 60),
}
_hits: dict[tuple[str, str, str], deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def rule_for(method: str, path: str) -> tuple[str, int, int] | None:
    best = None
    for (m, prefix), (n, win) in LIMITS.items():
        if m == method and path.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, n, win)
    return (best[0], best[1], best[2]) if best else None


def check_limit(ip: str, method: str, path: str, now: float | None = None) -> int | None:
    """Returns seconds to wait if the client is over its limit, else None (and records the hit)."""
    rule = rule_for(method, path)
    if rule is None:
        return None
    prefix, n, win = rule
    now = now if now is not None else time.monotonic()
    q = _hits[(ip, method, prefix)]
    while q and now - q[0] > win:
        q.popleft()
    if len(q) >= n:
        return max(1, int(win - (now - q[0])))
    q.append(now)
    return None


def reset_limits() -> None:
    _hits.clear()


def assert_prod_secrets() -> None:
    if settings.APP_ENV == "prod":
        bad = [k for k in ("ADMIN_TOKEN", "BACKOFFICE_PASSWORD") if getattr(settings, k) in ("change-me", "")]
        if bad:
            raise RuntimeError(f"Refusing to start in prod with default secrets: {', '.join(bad)}")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _guard(request: Request, call_next):
        if settings.RATE_LIMIT_ENABLED:
            wait = check_limit(client_ip(request), request.method, request.url.path)
            if wait is not None:
                return JSONResponse({"error": {"code": "RATE_LIMITED", "message_key": "common.rate_limited", "params": {"retry_after": wait}, "message": "Too many requests"}},
                                    status_code=429, headers={"Retry-After": str(wait)})
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Cache-Control", "no-store")  # API responses carry personal data
        return resp
