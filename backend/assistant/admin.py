"""The platform admin's view across every business: who is on the platform, what needs attention, what it costs, every call."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from lab.db import get_session
from lab.models import BoardItem, Business, Call, utcnow
from lab.schemas import Strict
from lab.service import ServiceError, iso

from lab import settings_store

from . import board, config, costs, service, tenant, whatsapp
from .access import admin_only, scope

router = APIRouter(prefix="/admin", dependencies=[Depends(scope), Depends(admin_only)])


def _box(request: Request):
    return request.app.state.lab_secret_box


def _base(request: Request) -> str:
    from .router import public_base

    return public_base(request)


def _link(request: Request, key: str) -> str:
    return f"{_base(request)}/assistant/?k={key}"


def _profile(b: Business) -> dict:
    return {**service.DEFAULT_PROFILE, **((b.settings or {}).get("profile") or {})}


def _rows(session: Session, days: int = 30) -> list[dict]:
    """One row per business: setup state, this period's calls and cost, board freshness."""
    since = utcnow() - timedelta(days=days)
    month = config.month_start()
    businesses = list(session.scalars(select(Business).order_by(Business.created_at)))
    calls: dict[str, list] = defaultdict(list)
    for biz_id, cost, imp, reviewed, status, handled, started in session.execute(
            select(Call.business_id, Call.cost, Call.importance, Call.reviewed, Call.status, Call.handled_by, Call.started_at).where(Call.started_at >= min(since, month))):
        calls[biz_id].append((cost or {}, imp, reviewed, status, handled, board._aware(started)))
    last = dict(session.execute(select(Call.business_id, func.max(Call.started_at)).where(Call.handled_by == "assistant").group_by(Call.business_id)).all())
    items: dict[str, list[BoardItem]] = defaultdict(list)
    for item in session.scalars(select(BoardItem)):
        items[item.business_id].append(item)
    out = []
    for b in businesses:
        p, mine = _profile(b), calls.get(b.id, [])
        stale_days = int(((b.settings or {}).get("knowledge") or {}).get("stale_days", 2))
        budget = (b.settings or {}).get("budget") or {}
        spend_month = round(sum(float(c.get("total") or 0) for c, *_rest, started in mine if started >= month), 2)
        in_period = [m for m in mine if m[5] >= since]
        answered = [m for m in in_period if m[4] == "assistant" and m[3] == "done"]
        out.append({
            "id": b.id, "name": b.name, "owner_name": p["owner_name"], "owner_phone": p["owner_phone"], "active": b.active, "phone_number": b.phone_number,
            "mode": p["mode"], "assistant_on": p["assistant_on"], "profile_ready": bool(p["business_name"] and p["owner_name"]), "has_link": bool(b.key_hash),
            "calls": len(answered), "needs_action": sum(1 for m in mine if m[4] == "assistant" and m[3] == "done" and m[1] == "action" and not m[2]),
            "cost": round(sum(float(m[0].get("total") or 0) for m in in_period), 2), "cost_month": spend_month, "budget": int(budget.get("monthly_inr") or 0), "hard_stop": bool(budget.get("hard_stop")),
            "items": len(items.get(b.id, [])), "stale_items": sum(1 for i in items.get(b.id, []) if board.is_stale(i, stale_days)),
            "last_call_at": iso(last.get(b.id)) if last.get(b.id) else None, "created_at": iso(b.created_at),
        })
    return out


def _attention(rows: list[dict]) -> list[dict]:
    notes = []
    for r in rows:
        def add(kind, text, level="warn"):
            notes.append({"business_id": r["id"], "business": r["name"], "kind": kind, "text": text, "level": level})
        if not r["active"]:
            add("paused", "Paused: the AI does not answer its calls", "info")
            continue
        if not r["profile_ready"]:
            add("setup", "Owner has not added their name and business name yet")
        if not r["phone_number"]:
            add("phone", "No Munshi phone number assigned, so phone calls cannot reach it")
        if not r["assistant_on"]:
            add("off", "The owner has switched the assistant off")
        if r["budget"] and r["cost_month"] >= r["budget"]:
            add("budget", f"Reached its monthly budget (Rs {r['cost_month']:.0f} of Rs {r['budget']})", "bad")
        if r["stale_items"]:
            add("stale", f"{r['stale_items']} of {r['items']} prices are out of date")
        if r["needs_action"] >= 5:
            add("backlog", f"{r['needs_action']} calls are waiting for the owner")
        if not r["has_link"]:
            add("link", "No owner link created yet", "info")
    order = {"bad": 0, "warn": 1, "info": 2}
    return sorted(notes, key=lambda n: order[n["level"]])


# --- businesses ---------------------------------------------------------------------------------

class BusinessIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    owner_name: str = Field(default="", max_length=80)
    owner_phone: str = Field(default="", max_length=20)
    phone_number: str = Field(default="", max_length=20)


class BusinessUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone_number: str | None = Field(default=None, max_length=20)
    active: bool | None = None


def _number(session: Session, raw: str, mine: str | None = None) -> str:
    if not raw.strip():
        return ""
    n = service.normalize_phone(raw)
    other = session.scalar(select(Business).where(Business.phone_number == n, Business.id != (mine or "")))
    if other:
        raise ServiceError(f"{n} already belongs to {other.name}.", 409)
    return n


def _issue_key(session: Session, request: Request, b: Business) -> str:
    key = tenant.new_key()
    b.key_hash = tenant.hash_key(key)
    b.key_enc = _box(request).encrypt(key) if _box(request) else None
    session.flush()
    return key


@router.get("/businesses")
def list_businesses(q: str = Query("", max_length=60), days: int = Query(30, ge=1, le=365), session: Session = Depends(get_session)):
    rows = _rows(session, days)
    if q.strip():
        needle = q.strip().lower()
        rows = [r for r in rows if needle in r["name"].lower() or needle in r["owner_name"].lower() or needle in r["phone_number"]]
    return {"items": rows, "days": days}


@router.post("/businesses", status_code=201)
def create_business(body: BusinessIn, request: Request, session: Session = Depends(get_session)):
    owner_phone = service.normalize_phone(body.owner_phone) if body.owner_phone else ""
    b = Business(name=body.name.strip(), phone_number=_number(session, body.phone_number), settings={"profile": {**service.DEFAULT_PROFILE, "business_name": body.name.strip(), "owner_name": body.owner_name.strip(), "owner_phone": owner_phone}})
    session.add(b)
    session.flush()
    key = _issue_key(session, request, b)
    config.audit(session, "business", f"Business “{b.name}” added", business_id=b.id)
    return {"id": b.id, "name": b.name, "link": _link(request, key)}


@router.get("/businesses/{business_id}")
def get_business(business_id: str, session: Session = Depends(get_session)):
    row = next((r for r in _rows(session) if r["id"] == business_id), None)
    if row is None:
        raise ServiceError("Business not found.", 404)
    return row


@router.put("/businesses/{business_id}")
def update_business(business_id: str, body: BusinessUpdate, session: Session = Depends(get_session)):
    b = tenant.business(session, business_id)
    if body.name is not None:
        b.name = body.name.strip()
        profile = {**_profile(b), "business_name": b.name}
        b.settings = {**(b.settings or {}), "profile": profile}
    if body.phone_number is not None:
        b.phone_number = _number(session, body.phone_number, b.id)
    if body.active is not None and body.active != b.active:
        b.active = body.active
        config.audit(session, "business", "Business " + ("resumed" if b.active else "paused"), business_id=b.id)
    session.flush()
    config.audit(session, "business", "Business details changed by the platform admin", business_id=b.id)
    return get_business(business_id, session)


@router.get("/businesses/{business_id}/link")
def show_link(business_id: str, request: Request, session: Session = Depends(get_session)):
    """The owner's private link, if it can still be shown."""
    b = tenant.business(session, business_id)
    key = _box(request).decrypt(b.key_enc) if (b.key_enc and _box(request)) else None
    return {"link": _link(request, key) if key else None, "has_link": bool(b.key_hash)}


@router.post("/businesses/{business_id}/link")
def new_link(business_id: str, request: Request, session: Session = Depends(get_session)):
    """Make a new private link. The old one stops working at once."""
    b = tenant.business(session, business_id)
    key = _issue_key(session, request, b)
    config.audit(session, "business", "New owner link created; the old one no longer works", business_id=b.id)
    return {"link": _link(request, key)}


class DeleteIn(Strict):
    confirm_name: str = Field(max_length=120)


@router.post("/businesses/{business_id}/delete", status_code=204)
def delete_business(business_id: str, body: DeleteIn, session: Session = Depends(get_session)):
    b = tenant.business(session, business_id)
    if body.confirm_name.strip().lower() != b.name.strip().lower():
        raise ServiceError("Type the business's exact name to delete it and all its calls.", 422)
    config.audit(session, "business", f"Business “{b.name}” deleted", business_id=None)
    session.delete(b)
    return Response(status_code=204)


# --- across the platform ------------------------------------------------------------------------

@router.get("/overview")
def overview(days: int = Query(30, ge=1, le=365), session: Session = Depends(get_session)):
    rows = _rows(session, days)
    since = utcnow() - timedelta(days=days)
    names = {r["id"]: r["name"] for r in rows}
    recent = session.scalars(select(Call).where(Call.handled_by == "assistant", Call.status == "done").order_by(Call.started_at.desc()).limit(8)).all()
    daily: dict[str, dict] = {}
    for started, cost in session.execute(select(Call.started_at, Call.cost).where(Call.started_at >= since, Call.status == "done")):
        d = started.date().isoformat()
        row = daily.setdefault(d, {"date": d, "calls": 0, "cost": 0.0})
        row["calls"] += 1
        row["cost"] += float((cost or {}).get("total") or 0)
    calls = sum(r["calls"] for r in rows)
    total = round(sum(r["cost"] for r in rows), 2)
    return {
        "days": days, "businesses": len(rows), "active": sum(1 for r in rows if r["active"]), "calls": calls, "needs_action": sum(r["needs_action"] for r in rows),
        "cost": total, "per_call": round(total / calls, 2) if calls else 0.0,
        "attention": _attention(rows), "daily": [{**v, "cost": round(v["cost"], 2)} for _, v in sorted(daily.items())],
        "top": sorted(({"id": r["id"], "name": r["name"], "calls": r["calls"], "cost": r["cost"]} for r in rows), key=lambda r: -r["calls"])[:5],
        "recent": [{**service.call_summary(c), "business_id": c.business_id, "business": names.get(c.business_id, "")} for c in recent],
    }


@router.get("/calls")
def all_calls(business: str = Query("", max_length=32), importance: str | None = Query(None, pattern="^(action|fyi|ignore)$"), q: str | None = Query(None, max_length=100),
              open_only: bool = False, limit: int = Query(40, ge=1, le=100), offset: int = Query(0, ge=0), session: Session = Depends(get_session)):
    query = select(Call).where(Call.handled_by == "assistant", Call.status == "done")
    if business:
        query = query.where(Call.business_id == business)
    if importance:
        query = query.where(Call.importance == importance)
    if open_only:
        query = query.where(Call.importance == "action", Call.reviewed.is_(False))
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(or_(Call.summary.ilike(like, escape="\\"), Call.caller_name.ilike(like, escape="\\"), Call.caller_number.ilike(like, escape="\\")))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.order_by(Call.started_at.desc()).limit(limit).offset(offset)).all()
    names = dict(session.execute(select(Business.id, Business.name)).all())
    return {"total": total, "items": [{**service.call_summary(c), "business_id": c.business_id, "business": names.get(c.business_id, "")} for c in rows]}


@router.get("/calls/{call_id}")
def call_detail(call_id: str, session: Session = Depends(get_session)):
    owner = session.scalar(select(Call.business_id).where(Call.id == call_id))
    if not owner:
        raise ServiceError("Call not found", 404)
    with tenant.acting_as(owner):
        return {**service.call_detail(service.load_call(session, call_id)), "business_id": owner, "business": tenant.business(session, owner).name}


@router.get("/costs")
def platform_costs(days: int = Query(30, ge=1, le=365), session: Session = Depends(get_session)):
    """Cost by business and by part, across the whole platform."""
    since = utcnow() - timedelta(days=days)
    names = dict(session.execute(select(Business.id, Business.name)).all())
    per: dict[str, dict] = {}
    by_part: dict[str, float] = defaultdict(float)
    per_day: dict[str, dict] = {}
    minutes = 0.0
    for biz_id, cost, started, duration in session.execute(select(Call.business_id, Call.cost, Call.started_at, Call.duration_s).where(Call.started_at >= since, Call.status == "done")):
        cost = cost or {}
        if not cost.get("total"):
            continue
        row = per.setdefault(biz_id, {"id": biz_id, "name": names.get(biz_id, ""), "calls": 0, "total": 0.0, **{p: 0.0 for p in costs.PARTS}})
        row["calls"] += 1
        row["total"] += float(cost["total"])
        for part in costs.PARTS:
            row[part] += float(cost.get(part) or 0)
            by_part[part] += float(cost.get(part) or 0)
        day = per_day.setdefault(started.date().isoformat(), {"date": started.date().isoformat(), "total": 0.0, "calls": 0})
        day["total"] += float(cost["total"])
        day["calls"] += 1
        minutes += (duration or 0) / 60
    total = sum(by_part.values())
    calls = sum(r["calls"] for r in per.values())
    rows = sorted(({**r, **{k: round(v, 2) for k, v in r.items() if isinstance(v, float)}, "per_call": round(r["total"] / r["calls"], 2) if r["calls"] else 0.0} for r in per.values()), key=lambda r: -r["total"])
    return {"days": days, "calls": calls, "minutes": round(minutes, 1), "total": round(total, 2), "per_call": round(total / calls, 2) if calls else 0.0,
            "parts": [{"id": p, "label": costs.LABELS[p], "amount": round(by_part[p], 2), "share": round(by_part[p] / total, 3) if total else 0.0} for p in costs.PARTS],
            "businesses": rows, "daily": [{**v, "total": round(v["total"], 2)} for _, v in sorted(per_day.items())], "unit_prices": [{"item": a, "price": b} for a, b in costs.UNIT_PRICES],
            "note": "Estimated in rupees from published list prices. Number rental (Rs 200 a month per number) is not included."}


@router.get("/platform")
def platform_info(request: Request, session: Session = Depends(get_session)):
    """What the platform's own connections look like (Plivo account, WhatsApp, webhook addresses) and whether sign-in is on."""
    box = _box(request)
    base = _base(request)
    cfg = request.app.state.lab_settings
    return {"phone": settings_store.phone_status(session, box), "whatsapp": {**settings_store.whatsapp_status(session, box), "template_body": whatsapp.TEMPLATE_BODY},
            "webhooks": {"answer": f"{base}/telephony/plivo/answer", "hangup": f"{base}/telephony/plivo/hangup", "https": base.startswith("https://")},
            "signed_in_required": bool(cfg.api_tokens) and not cfg.open_access}
