"""Web Push notification support using VAPID.

The pywebpush library is optional — if it cannot be installed (http-ece build
failure), push notifications are silently disabled and ``configured()`` returns
False.  The env vars MUNSHI_VAPID_PRIVATE_KEY and MUNSHI_VAPID_PUBLIC_KEY are
the base64url-encoded VAPID key pair.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("ai_therapy.assistant.push")

VAPID_PRIVATE = os.getenv("MUNSHI_VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC = os.getenv("MUNSHI_VAPID_PUBLIC_KEY", "")
VAPID_EMAIL = os.getenv("MUNSHI_VAPID_EMAIL", "mailto:hello@munshi.app")

try:
    from pywebpush import WebPushException, webpush
    _HAS_LIB = True
except ImportError:
    _HAS_LIB = False


def configured() -> bool:
    return _HAS_LIB and bool(VAPID_PRIVATE and VAPID_PUBLIC)


def public_key() -> str:
    return VAPID_PUBLIC


def send_sync(subscription: dict, title: str, body: str, url: str = "/assistant/") -> bool:
    if not configured():
        return False
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE,
            vapid_claims={"sub": VAPID_EMAIL},
        )
        return True
    except Exception as exc:
        logger.debug("push failed: %s", exc)
        return False


async def notify_owner(business_id: int, title: str, body: str, url: str = "/assistant/") -> int:
    """Send push to all subscriptions for a business. Returns how many were sent."""
    if not configured():
        return 0
    from lab.runner import run_db
    from lab import settings_store

    subs = await run_db(lambda s: settings_store.get(s, "push_subscriptions", []) or [])
    sent = 0
    for sub in subs:
        if send_sync(sub, title, body, url):
            sent += 1
    return sent
