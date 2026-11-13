"""Settings the owner changes from the portal. Each lives in the database, so a change reaches the very next call."""
from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab import settings_store
from lab.models import AuditEntry, Call, utcnow
from lab.service import ServiceError, iso

KNOWLEDGE_KEY, BUDGET_KEY, PROMPTS_KEY = "assistant.knowledge", "assistant.budget", "assistant.prompts"
MAX_HISTORY = 20


# --- the trail of changes ------------------------------------------------------------

def audit(session: Session, area: str, summary: str) -> None:
    session.add(AuditEntry(area=area[:20], summary=summary[:300]))
    # keep the table small: the newest 500 entries are enough for a "what changed" view
    count = session.scalar(select(func.count()).select_from(AuditEntry)) or 0
    if count > 520:
        old = session.scalars(select(AuditEntry).order_by(AuditEntry.created_at).limit(count - 500)).all()
        for row in old:
            session.delete(row)


def activity(session: Session, limit: int = 60, area: str | None = None) -> list[dict]:
    q = select(AuditEntry).order_by(AuditEntry.created_at.desc()).limit(limit)
    if area:
        q = q.where(AuditEntry.area == area)
    return [{"id": a.id, "area": a.area, "summary": a.summary, "at": iso(a.created_at)} for a in session.scalars(q)]


# --- how long a price or stock level is trusted --------------------------------------

class KnowledgeIn(BaseModel):
    stale_days: int = Field(default=2, ge=0, le=30)  # 0 = never treat as out of date
    model_config = {"extra": "forbid"}


def get_knowledge(session: Session) -> dict:
    return {"stale_days": 2, **(settings_store.get(session, KNOWLEDGE_KEY, {}) or {})}


def save_knowledge(session: Session, body: KnowledgeIn) -> dict:
    settings_store.put(session, KNOWLEDGE_KEY, body.model_dump())
    audit(session, "board", f"Prices count as out of date after {body.stale_days} day(s)" if body.stale_days else "Prices never count as out of date")
    return get_knowledge(session)


# --- monthly budget ------------------------------------------------------------------

class BudgetIn(BaseModel):
    monthly_inr: int = Field(default=0, ge=0, le=10_000_000)  # 0 = no budget set
    hard_stop: bool = False
    model_config = {"extra": "forbid"}


def get_budget(session: Session) -> dict:
    return {"monthly_inr": 0, "hard_stop": False, **(settings_store.get(session, BUDGET_KEY, {}) or {})}


def save_budget(session: Session, body: BudgetIn) -> dict:
    settings_store.put(session, BUDGET_KEY, body.model_dump())
    audit(session, "budget", f"Monthly budget set to Rs {body.monthly_inr:,}{' with a hard stop' if body.hard_stop else ''}" if body.monthly_inr else "Monthly budget removed")
    return get_budget(session)


def month_start():
    now = utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_spend(session: Session) -> float:
    rows = session.scalars(select(Call.cost).where(Call.started_at >= month_start())).all()
    return round(sum(float((c or {}).get("total") or 0) for c in rows), 2)


def over_budget(session: Session) -> bool:
    b = get_budget(session)
    return bool(b["hard_stop"] and b["monthly_inr"] and month_spend(session) >= b["monthly_inr"])


# --- the parts of the prompts the owner may change -----------------------------------

class PromptsIn(BaseModel):
    extra: str = Field(default="", max_length=1500)          # more instructions for the phone assistant
    greeting: str = Field(default="", max_length=300)        # opening line; {business} and {owner} are filled in
    summary_rules: str = Field(default="", max_length=800)   # more rules for the call notes
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


EMPTY_PROMPTS = {"extra": "", "greeting": "", "summary_rules": ""}


def _stored_prompts(session: Session) -> dict:
    stored = settings_store.get(session, PROMPTS_KEY, {}) or {}
    return {"version": int(stored.get("version", 0)), **{k: stored.get(k, "") for k in EMPTY_PROMPTS}, "history": list(stored.get("history", []))}


def get_prompts(session: Session) -> dict:
    """The live values the assistant uses (empty strings mean "use the built-in text")."""
    s = _stored_prompts(session)
    return {k: s[k] for k in EMPTY_PROMPTS} | {"version": s["version"]}


def prompts_with_history(session: Session) -> dict:
    s = _stored_prompts(session)
    return {**s, "history": [{**h, "at": h.get("at")} for h in reversed(s["history"])]}


def save_prompts(session: Session, values: dict, note: str = "") -> dict:
    s = _stored_prompts(session)
    if all(values.get(k, "") == s[k] for k in EMPTY_PROMPTS):
        return get_prompts(session)
    version = s["version"] + 1
    history = (s["history"] + [{"version": s["version"], "at": iso(utcnow()), **{k: s[k] for k in EMPTY_PROMPTS}}])[-MAX_HISTORY:] if s["version"] else s["history"]
    settings_store.put(session, PROMPTS_KEY, {"version": version, **{k: values.get(k, "") for k in EMPTY_PROMPTS}, "history": history})
    audit(session, "prompts", note or f"Prompts changed (version {version})")
    return get_prompts(session)


def restore_prompts(session: Session, version: int) -> dict:
    s = _stored_prompts(session)
    old = next((h for h in s["history"] if h.get("version") == version), None)
    if old is None:
        raise ServiceError("That version is no longer kept.", 404)
    return save_prompts(session, {k: old.get(k, "") for k in EMPTY_PROMPTS}, f"Prompts restored to version {version}")
