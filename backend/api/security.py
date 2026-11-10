"""Small, dependency-free protections for the web API.

- Security headers on every response.
- A cross-site check on requests that change something.
- A limit on wrong passwords, per account and address.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    # The API only ever returns data, so nothing may load or frame from it.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}
MAX_FAILURES = 5
WINDOW_SECONDS = 300
_failures: dict[str, deque] = defaultdict(deque)


def cookie_secure() -> bool:
    """Send the session cookie over HTTPS only. Set SP_COOKIE_SECURE=1 wherever the app is served over HTTPS."""
    return os.environ.get("SP_COOKIE_SECURE", "0") == "1"


def demo_logins_enabled() -> bool:
    """The test log-ins are shown on the sign-in screen for the demo. Set SP_DEMO_LOGINS=0 to hide them."""
    return os.environ.get("SP_DEMO_LOGINS", "1") != "0"


async def security_middleware(request: Request, call_next):
    # A browser sends Origin on cross-site POSTs. If it names another site, refuse.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "This request came from another site and was refused."}, status_code=403,
                                headers=HEADERS)
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/docs") or path.startswith("/api/openapi"):
        response.headers["X-Content-Type-Options"] = "nosniff"       # the docs page needs its own scripts
        return response
    for name, value in HEADERS.items():
        response.headers.setdefault(name, value)
    return response


def _key(username: str, request: Request) -> str:
    return f"{username.strip().lower()}|{request.client.host if request.client else 'unknown'}"


def too_many_failures(username: str, request: Request) -> bool:
    recent = _failures[_key(username, request)]
    while recent and time.time() - recent[0] > WINDOW_SECONDS:
        recent.popleft()
    return len(recent) >= MAX_FAILURES


def record_failure(username: str, request: Request) -> None:
    _failures[_key(username, request)].append(time.time())


def clear_failures(username: str, request: Request) -> None:
    _failures.pop(_key(username, request), None)
