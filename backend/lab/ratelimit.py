"""A small in-memory sliding-window limiter, and the caller's real address.

Limits protect the money (AI, voice and SMS calls cost per use) and block guessing. One worker process, so memory is enough.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_HITS: dict[str, deque] = defaultdict(deque)
_MAX_KEYS = 20000


def client_ip(request: Request) -> str:
    """The visitor's address. Cloudflare sets CF-Connecting-IP; otherwise the LAST X-Forwarded-For hop is the one our own proxy added.
    The first hop is whatever the visitor chose to send, so it is never trusted."""
    cf = request.headers.get("cf-connecting-ip", "").strip()
    if cf:
        return cf[:45]
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    return (hops[-1] if hops else (request.client.host if request.client else "unknown"))[:45]


def hit(key: str, limit: int, window: int = 60) -> None:
    now = time.monotonic()
    q = _HITS[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many requests. Please slow down and try again in a minute.", headers={"Retry-After": str(window)})
    q.append(now)
    if len(_HITS) > _MAX_KEYS:  # keep memory bounded
        for k in [k for k, v in _HITS.items() if not v or now - v[-1] > window][:5000]:
            _HITS.pop(k, None)


def reset() -> None:
    _HITS.clear()
    from . import security

    security.reset_throttle()
