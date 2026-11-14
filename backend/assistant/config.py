"""Settings the owner or the platform admin changes from the portal. Each lives in the database, so a change reaches the very next call."""
from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab import settings_store
from lab.models import AuditEntry, Business, Call, utcnow
from lab.service import ServiceError, iso

from . import prompts, tenant

TEMPLATES_KEY = "assistant.templates"  # platform-wide default texts (Setting table)
MAX_HISTORY = 20


# --- the trail of changes ------------------------------------------------------------

def audit(session: Session, area: str, summary: str, *, business_id: str | None = "current") -> None:
    """Record a change. By default it belongs to the business being worked on; pass ``business_id=None`` for platform-wide changes."""
    biz = tenant.active_id() if business_id == "current" else business_id
    session.add(AuditEntry(area=area[:20], summary=summary[:300], business_id=biz))
    # keep the table small: the newest 2,000 entries are enough for a "what changed" view
    count = session.scalar(select(func.count()).select_from(AuditEntry)) or 0
    if count > 2050:
        old = session.scalars(select(AuditEntry).order_by(AuditEntry.created_at).limit(count - 2000)).all()
        for row in old:
            session.delete(row)


def activity(session: Session, limit: int = 60, area: str | None = None, *, business_id: str | None = None, everyone: bool = False) -> list[dict]:
    """The trail for one business, or (``everyone``) for the whole platform with the business named on each row."""
    q = select(AuditEntry, Business.name).outerjoin(Business, Business.id == AuditEntry.business_id).order_by(AuditEntry.created_at.desc()).limit(limit)
    if not everyone:
        q = q.where(AuditEntry.business_id == (business_id or tenant.current()))
    if area:
        q = q.where(AuditEntry.area == area)
    return [{"id": a.id, "area": a.area, "summary": a.summary, "at": iso(a.created_at), "business_id": a.business_id, "business": name or "Platform"} for a, name in session.execute(q)]


# --- how long a price or stock level is trusted --------------------------------------

class KnowledgeIn(BaseModel):
    stale_days: int = Field(default=2, ge=0, le=30)  # 0 = never treat as out of date
    model_config = {"extra": "forbid"}


def get_knowledge(session: Session) -> dict:
    return {"stale_days": 2, **(tenant.get(session, "knowledge", {}) or {})}


def save_knowledge(session: Session, body: KnowledgeIn) -> dict:
    tenant.put(session, "knowledge", body.model_dump())
    audit(session, "board", f"Prices count as out of date after {body.stale_days} day(s)" if body.stale_days else "Prices never count as out of date")
    return get_knowledge(session)


# --- monthly budget ------------------------------------------------------------------

class BudgetIn(BaseModel):
    monthly_inr: int = Field(default=0, ge=0, le=10_000_000)  # 0 = no budget set
    hard_stop: bool = False
    model_config = {"extra": "forbid"}


def get_budget(session: Session) -> dict:
    return {"monthly_inr": 0, "hard_stop": False, **(tenant.get(session, "budget", {}) or {})}


def save_budget(session: Session, body: BudgetIn) -> dict:
    tenant.put(session, "budget", body.model_dump())
    audit(session, "budget", f"Monthly budget set to Rs {body.monthly_inr:,}{' with a hard stop' if body.hard_stop else ''}" if body.monthly_inr else "Monthly budget removed")
    return get_budget(session)


def month_start():
    now = utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_spend(session: Session, business_id: str | None = None) -> float:
    rows = session.scalars(select(Call.cost).where(Call.business_id == (business_id or tenant.current()), Call.started_at >= month_start())).all()
    return round(sum(float((c or {}).get("total") or 0) for c in rows), 2)


def over_budget(session: Session) -> bool:
    b = get_budget(session)
    return bool(b["hard_stop"] and b["monthly_inr"] and month_spend(session) >= b["monthly_inr"])


# --- prompt templates: platform default, optional override per business ----------------------

def _blank() -> dict:
    return {"version": 0, "values": {}, "history": []}


def _load(session: Session, scope: str) -> dict:
    stored = (settings_store.get(session, TEMPLATES_KEY, {}) if scope == "platform" else tenant.get(session, "templates", {})) or {}
    return {**_blank(), **stored}


def _store(session: Session, scope: str, data: dict) -> None:
    if scope == "platform":
        settings_store.put(session, TEMPLATES_KEY, data)
    else:
        tenant.put(session, "templates", data)


def _check_scope(scope: str) -> None:
    if scope not in ("platform", "business"):
        raise ServiceError("Unknown scope.", 422)


def resolve(session: Session, kind: str) -> str:
    """The text a call uses: this business's own version, else the platform's, else the built-in (empty means built-in)."""
    own = (_load(session, "business")["values"].get(kind) or "").strip() if tenant.active_id() else ""
    return own or (_load(session, "platform")["values"].get(kind) or "").strip()


def template_view(session: Session, scope: str) -> dict:
    """What the prompt editor shows for the platform default (``platform``) or for the current business (``business``)."""
    _check_scope(scope)
    mine = _load(session, scope)
    platform = _load(session, "platform")["values"]
    templates = {}
    for kind in prompts.KINDS:
        own = (mine["values"].get(kind) or "").strip()
        inherited = (platform.get(kind) or "").strip() or prompts.DEFAULTS[kind]
        templates[kind] = {
            "label": prompts.KIND_LABELS[kind], "help": prompts.KIND_HELP[kind], "value": own or inherited, "own": bool(own),
            "inherited": inherited, "default": prompts.DEFAULTS[kind], "locked": prompts.LOCKED.get(kind, ""),
            "variables": [{"name": n, "description": d} for n, d in prompts.variables_for(kind).items()],
        }
    return {"scope": scope, "version": mine["version"], "templates": templates,
            "history": [{"version": h["version"], "at": h["at"], "kinds": sorted(k for k, v in h["values"].items() if v)} for h in reversed(mine["history"])]}


def save_templates(session: Session, scope: str, values: dict, note: str = "") -> dict:
    """Save the given templates. A blank or unchanged-from-inherited text clears the override, so the template follows the platform again."""
    _check_scope(scope)
    mine = _load(session, scope)
    new = dict(mine["values"])
    for kind, text in values.items():
        if kind not in prompts.KINDS:
            raise ServiceError(f"Unknown prompt “{kind}”.", 422)
        text = (text or "").strip()
        bad = prompts.unknown_variables(kind, text)
        if bad:
            raise ServiceError(f"{prompts.KIND_LABELS[kind]}: unknown variable {', '.join('{{' + b + '}}' for b in bad)}. Use: {', '.join('{{' + n + '}}' for n in prompts.variables_for(kind))}.", 422)
        if len(text) > 12000:
            raise ServiceError(f"{prompts.KIND_LABELS[kind]} is too long (12,000 characters at most).", 422)
        inherited = ((_load(session, "platform")["values"].get(kind) or "").strip() if scope == "business" else "") or prompts.DEFAULTS[kind]
        if text and text != inherited:
            new[kind] = text
        else:
            new.pop(kind, None)
    if new == mine["values"]:
        return template_view(session, scope)
    history = (mine["history"] + [{"version": mine["version"], "at": iso(utcnow()), "values": mine["values"]}])[-MAX_HISTORY:] if mine["version"] else mine["history"]
    _store(session, scope, {"version": mine["version"] + 1, "values": new, "history": history})
    changed = ", ".join(prompts.KIND_LABELS[k] for k in sorted(set(values)))
    audit(session, "prompts", note or f"{'Platform default' if scope == 'platform' else 'Business'} prompts changed: {changed} (version {mine['version'] + 1})", business_id=None if scope == "platform" else "current")
    return template_view(session, scope)


def restore_templates(session: Session, scope: str, version: int) -> dict:
    _check_scope(scope)
    mine = _load(session, scope)
    old = next((h for h in mine["history"] if h.get("version") == version), None)
    if old is None:
        raise ServiceError("That version is no longer kept.", 404)
    new = dict(old["values"])
    history = (mine["history"] + [{"version": mine["version"], "at": iso(utcnow()), "values": mine["values"]}])[-MAX_HISTORY:]
    _store(session, scope, {"version": mine["version"] + 1, "values": new, "history": history})
    audit(session, "prompts", f"Prompts restored to version {version}", business_id=None if scope == "platform" else "current")
    return template_view(session, scope)


def render_preview(session: Session, kind: str, text: str, profile: dict, items) -> dict:
    """What the model would actually receive for ``text``, filled in with this business's real details."""
    if kind not in prompts.KINDS:
        raise ServiceError("Unknown prompt.", 422)
    from . import lexicon
    values = prompts.values_for(profile, items, caller_name="Ravi", caller_number="+919876543210", today=utcnow().strftime("%d %B %Y"), local_words=lexicon.local_words_block(lexicon.effective(session)))
    body = prompts.fill((text or "").strip() or prompts.DEFAULTS[kind], values).rstrip()
    locked = prompts.fill(prompts.LOCKED.get(kind, ""), values)
    return {"text": body, "locked": locked, "unknown": prompts.unknown_variables(kind, text or ""), "used": prompts.used_variables(text or ""),
            "words": len((body + " " + locked).split()), "values": {k: v for k, v in values.items() if k in prompts.variables_for(kind)}}
