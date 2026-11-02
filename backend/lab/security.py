"""Bearer-token auth for the lab API, plus a small in-memory brute-force throttle."""
from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_FAILURES: dict[str, deque] = defaultdict(deque)
WINDOW_S = 60
MAX_FAILURES = 10


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def reset_throttle() -> None:
    _FAILURES.clear()


def require_auth(request: Request) -> None:
    settings = request.app.state.lab_settings
    if settings.open_access or not settings.api_tokens:  # sign-in switched off on purpose (LAB_OPEN_ACCESS) or local development
        return
    who = _client(request)
    now = time.monotonic()
    recent = _FAILURES[who]
    while recent and now - recent[0] > WINDOW_S:
        recent.popleft()
    if len(recent) >= MAX_FAILURES:
        raise HTTPException(429, "Too many failed attempts. Try again in a minute.", headers={"Retry-After": str(WINDOW_S)})
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        presented = token.strip().encode()
        # check every token without short-circuiting on the first hit
        ok = False
        for valid in settings.api_tokens:
            ok |= hmac.compare_digest(presented, valid.encode())
        if ok:
            return
    recent.append(now)
    raise HTTPException(401, "Invalid or missing access token.", headers={"WWW-Authenticate": "Bearer"})
