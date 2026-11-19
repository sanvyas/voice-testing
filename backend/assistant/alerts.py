"""Things the platform operator must hear about: the AI provider failing or out of quota, SMS not going out, spend near the limit.

``raise_alert`` never raises and never blocks a call. One problem keeps one row (with a count), so a quota outage is one alert, not
ten thousand. A background loop sends new or repeating alerts to ``ALERT_WEBHOOK_URL`` (Slack, Discord, or anything that takes JSON).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta

import llm
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab import db
from lab.models import Alert, utcnow

logger = logging.getLogger("munshi.alerts")
NOTIFY_EVERY = timedelta(minutes=30)  # a problem that goes on is repeated, but not more often than this
_OPEN: set[str] = set()


def _aware(dt):
    from datetime import timezone
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite hands back naive times; Postgres aware ones


def raise_alert(key: str, title: str, detail: str = "", level: str = "warn", session: Session | None = None) -> None:
    def work(s: Session) -> None:
        row = s.scalar(select(Alert).where(Alert.key == key, Alert.resolved_at.is_(None)))
        now = utcnow()
        if row is None:
            s.add(Alert(key=key[:80], level=level, title=title[:160], detail=detail[:2000], created_at=now, last_at=now))
        else:
            row.count += 1
            row.last_at, row.detail, row.level = now, detail[:2000] or row.detail, level
        s.flush()
    try:
        if session is not None:
            work(session)
        else:
            with db.session_scope() as s:
                work(s)
        _OPEN.add(key)
    except Exception:  # noqa: BLE001
        logger.exception("could not record alert %s", key)


def clear(key: str) -> None:
    """The problem is gone (a call to the AI worked again): close its alert."""
    if key not in _OPEN:
        return
    _OPEN.discard(key)
    try:
        with db.session_scope() as s:
            for row in s.scalars(select(Alert).where(Alert.key == key, Alert.resolved_at.is_(None))):
                row.resolved_at = utcnow()
    except Exception:  # noqa: BLE001
        logger.exception("could not clear alert %s", key)


def llm_failed(exc: Exception) -> None:
    text = str(exc)
    if "429" in text or "quota" in text.lower() or "rate limit" in text.lower():
        raise_alert("llm-quota", "The AI provider's limit is reached", f"Calls cannot be answered until it resets or another provider is added. {text[:300]}", "error")
    else:
        raise_alert("llm", "The AI provider is failing", text[:400], "error")


def llm_ok() -> None:
    clear("llm")
    clear("llm-quota")


def out(a: Alert) -> dict:
    return {"id": a.id, "key": a.key, "level": a.level, "title": a.title, "detail": a.detail, "count": a.count, "first_at": a.created_at.isoformat(), "last_at": a.last_at.isoformat(), "open": a.resolved_at is None}


def listing(session: Session, limit: int = 50) -> dict:
    rows = list(session.scalars(select(Alert).order_by(Alert.resolved_at.is_(None).desc(), Alert.last_at.desc()).limit(limit)))
    return {"items": [out(a) for a in rows], "open": sum(1 for a in rows if a.resolved_at is None), "webhook": bool(os.getenv("ALERT_WEBHOOK_URL"))}


def resolve(session: Session, alert_id: str) -> bool:
    row = session.get(Alert, alert_id)
    if row is None:
        return False
    row.resolved_at = row.resolved_at or utcnow()
    _OPEN.discard(row.key)
    return True


async def notify_pending() -> int:
    """Send alerts that are new, or still happening and not reported for NOTIFY_EVERY. Returns how many went out."""
    url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not url:
        return 0
    with db.session_scope() as s:
        now = utcnow()
        due = [a for a in s.scalars(select(Alert).where(Alert.resolved_at.is_(None)))
               if a.notified_at is None or (_aware(a.last_at) > _aware(a.notified_at) and now - _aware(a.notified_at) >= NOTIFY_EVERY)]
        payloads = [(a.id, f"[{a.level.upper()}] Munshi: {a.title}\n{a.detail[:500]}\n(seen {a.count} time{'s' if a.count != 1 else ''})") for a in due]
    sent = 0
    for alert_id, text in payloads:
        try:
            r = await llm.http_client().post(url, json={"text": text, "content": text}, timeout=8)
            ok = r.status_code < 300
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            sent += 1
            with db.session_scope() as s:
                row = s.get(Alert, alert_id)
                if row:
                    row.notified_at = utcnow()
        else:
            logger.warning("alert webhook did not accept %s", alert_id)
    return sent


def check_budgets() -> None:
    """A business near or over its monthly budget is an alert for the operator (the owner sees it in their own app)."""
    from .admin import _rows

    with db.session_scope() as s:
        rows = _rows(s, 30)
    for r in rows:
        key = f"budget-{r['id']}"
        if r["budget"] and r["cost_month"] >= 0.8 * r["budget"]:
            over = r["cost_month"] >= r["budget"]
            raise_alert(key, f"{r['name']}: {'monthly budget used up' if over else 'monthly budget 80% used'}", f"Rs {r['cost_month']} of Rs {r['budget']} this month." + (" The AI stops answering." if over and r["hard_stop"] else ""), "error" if over else "warn")
        else:
            clear(key)


async def loop() -> None:
    n = 0
    while True:
        try:
            await notify_pending()
            if n % 15 == 0:
                await asyncio.to_thread(check_budgets)
        except Exception:  # noqa: BLE001
            logger.exception("alert delivery failed")
        n += 1
        await asyncio.sleep(60)
