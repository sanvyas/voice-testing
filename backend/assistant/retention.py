"""Keeping only what is needed: old calls, spent sign-in codes and ended sessions are deleted on a schedule."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from lab import db
from lab.models import Alert, Call, OtpCode, OwnerSession, WaMessage, utcnow

from . import alerts, legal

logger = logging.getLogger("munshi.retention")


def purge(session: Session, days: int | None = None) -> dict:
    days = days or legal.retention_days()
    now = utcnow()
    cutoff = now - timedelta(days=days)
    calls = list(session.scalars(select(Call).where(Call.started_at < cutoff, Call.status == "done").limit(2000)))
    for c in calls:  # one by one, so each call's turns and notes go with it
        session.delete(c)
    msgs = session.execute(delete(WaMessage).where(WaMessage.created_at < cutoff)).rowcount or 0
    codes = session.execute(delete(OtpCode).where(OtpCode.expires_at < now - timedelta(days=1))).rowcount or 0
    sessions = session.execute(delete(OwnerSession).where(OwnerSession.expires_at < now)).rowcount or 0
    old_alerts = session.execute(delete(Alert).where(Alert.resolved_at.is_not(None), Alert.resolved_at < now - timedelta(days=90))).rowcount or 0
    return {"calls": len(calls), "messages": msgs, "codes": codes, "sessions": sessions, "alerts": old_alerts, "older_than_days": days}


async def loop() -> None:
    await asyncio.sleep(120)
    while True:
        try:
            with db.session_scope() as s:
                out = purge(s)
            if any(out[k] for k in ("calls", "messages")):
                logger.info("retention: %s", out)
            alerts.clear("retention")
        except Exception as exc:  # noqa: BLE001
            logger.exception("retention purge failed")
            alerts.raise_alert("retention", "Old data could not be deleted on schedule", str(exc)[:300], "warn")
        await asyncio.sleep(24 * 3600)
