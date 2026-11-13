"""What the assistant costs, from the cost each call recorded. Rupees, estimated from published list prices."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import tts
from lab import settings_store
from lab.models import Call, utcnow
from lab.service import iso

from . import config

PARTS = ("phone", "voice", "ai", "speech_to_text", "whatsapp")
LABELS = {"phone": "Phone line", "voice": "Voice", "ai": "AI thinking", "speech_to_text": "Understanding speech", "whatsapp": "WhatsApp replies"}
UNIT_PRICES = [
    ("Phone line (Plivo, India)", "Rs 0.38 per minute in 30-second steps, Rs 200 a month per number"),
    ("Understanding speech (Groq Whisper turbo)", "$0.04 per hour of audio, at least 10 seconds each time"),
    ("AI thinking (Groq gpt-oss-20b)", "$0.075 per million input tokens, $0.30 per million output tokens"),
    ("Voice (Google Standard or WaveNet)", "$4 per million characters, first 4 million a month free"),
    ("Voice (Chatterbox on DeepInfra)", "$1 per million characters"),
    ("WhatsApp reply (utility message)", "about Rs 0.13 each, as listed by MyOperator; Meta's own rate card not checked"),
]


def overview(session: Session, days: int = 30) -> dict:
    since = utcnow() - timedelta(days=days)
    calls = list(session.scalars(select(Call).where(Call.started_at >= since, Call.status == "done").order_by(Call.started_at)))
    by_part: dict[str, float] = defaultdict(float)
    per_day: dict[str, dict] = {}
    minutes, priced = 0.0, 0
    for c in calls:
        cost = c.cost or {}
        if not cost.get("total"):
            continue
        priced += 1
        for part in PARTS:
            by_part[part] += float(cost.get(part) or 0)
        day = (c.started_at.date() if c.started_at else since.date()).isoformat()
        row = per_day.setdefault(day, {"date": day, "total": 0.0, "calls": 0})
        row["total"] += float(cost["total"])
        row["calls"] += 1
        minutes += (c.duration_s or 0) / 60
    total = sum(by_part.values())
    budget = config.get_budget(session)
    spend = config.month_spend(session)
    now = utcnow()
    day_of_month = max(1, now.day)
    days_in_month = (now.replace(month=now.month % 12 + 1, day=1) - timedelta(days=1)).day if now.month != 12 else 31
    projected = round(spend / day_of_month * days_in_month, 2)
    top = sorted((c for c in calls if (c.cost or {}).get("total")), key=lambda c: -c.cost["total"])[:5]
    usage = settings_store.tts_usage(session)
    voice_usage = []
    for engine, meta in tts.ENGINES.items():
        u = usage[engine]
        voice_usage.append({"label": meta["label"], "chars": u["chars"], "estimated_usd": round(max(0, u["chars"] - meta["free_chars"]) * meta["price_per_m"] / 1e6, 4), "reported_usd": u["cost_usd"] or None, "limit": tts.cap_chars(engine)})
    return {
        "days": days, "calls": len(calls), "priced_calls": priced, "minutes": round(minutes, 1), "total": round(total, 2),
        "per_call": round(total / priced, 2) if priced else 0.0, "per_minute": round(total / minutes, 2) if minutes else 0.0,
        "parts": [{"id": p, "label": LABELS[p], "amount": round(by_part[p], 2), "share": round(by_part[p] / total, 3) if total else 0.0} for p in PARTS],
        "daily": [{**v, "total": round(v["total"], 2)} for _, v in sorted(per_day.items())],
        "month": {"spend": spend, "projected": projected, "budget": budget["monthly_inr"], "hard_stop": budget["hard_stop"], "used": round(spend / budget["monthly_inr"], 3) if budget["monthly_inr"] else None},
        "top_calls": [{"id": c.id, "caller": c.caller_name or c.caller_number or "Unknown", "total": c.cost["total"], "at": iso(c.started_at)} for c in top],
        "voice_usage": voice_usage,
        "unit_prices": [{"item": a, "price": b} for a, b in UNIT_PRICES],
        "note": "Estimated in rupees from published list prices. Number rental (Rs 200 a month) is not included.",
    }
