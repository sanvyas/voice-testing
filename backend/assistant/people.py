"""The owner app's view of the business: people (one row per caller), the WhatsApp thread with each person,
the shop info page, who is always rung, and the plan. Everything here reads or writes the calls, messages, board and profile
that already exist; nothing is invented for display."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import llm
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab import settings_store
from lab.models import BoardItem, Business, Call, Contact, WaMessage, utcnow
from lab.runner import run_db
from lab.service import ServiceError, iso

from . import board, config, service, tenant

IST = timezone(timedelta(hours=5, minutes=30))
STALE_FACT_HOURS = 168
CALL_LIMIT = 100  # the plan's call allowance shown in the app (an example until pricing is final)
TRIAL_DAYS = 14


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _days_ago(dt: datetime) -> int:
    return max(0, (utcnow().astimezone(IST).date() - _aware(dt).astimezone(IST).date()).days)


def _is_pending(c: Call) -> bool:
    return c.importance == "action" and not c.reviewed


def _display_name(c: Call, names: dict[str, str]) -> str:
    return names.get(c.caller_number) or c.caller_name or c.caller_number or "Unknown caller"


def _calls(session: Session, limit: int = 600) -> list[Call]:
    return list(session.scalars(select(Call).where(Call.business_id == tenant.current(), Call.handled_by == "assistant", Call.status == "done")
                                .order_by(Call.started_at.desc()).limit(limit)))


def _contact_names(session: Session) -> dict[str, str]:
    return {c.phone: c.name for c in session.scalars(select(Contact).where(Contact.business_id == tenant.current()))}


# --- people: one row per caller -----------------------------------------------------------

def people(session: Session, tab: str = "need", q: str = "", rng: str = "any") -> dict:
    names = _contact_names(session)
    groups: dict[str, list[Call]] = {}
    for c in _calls(session):
        groups.setdefault(c.caller_number or f"call:{c.id}", []).append(c)
    needle = (q or "").strip().lower()
    limit = {"today": 0, "7d": 7, "30d": 30}.get(rng)
    rows = []
    for key, calls in groups.items():
        calls.sort(key=lambda c: _aware(c.started_at))
        calls = [c for c in calls if limit is None or _days_ago(c.started_at) <= limit]
        if not calls:
            continue
        pend = [c for c in calls if _is_pending(c)]
        last = pend[-1] if pend else calls[-1]
        name = _display_name(last, names)
        if needle and needle not in f"{name} {last.summary} {last.caller_number}".lower():
            continue
        kind = "need" if pend else ("good" if any(c.importance != "ignore" for c in calls) else "spam")
        rows.append({"key": key, "phone": last.caller_number, "name": name, "summary": last.summary, "ask": (last.meta or {}).get("ask", ""), "at": iso(last.started_at),
                     "days_ago": _days_ago(last.started_at), "calls": len(calls), "pending": len(pend), "oldest_pending_days": max((_days_ago(c.started_at) for c in pend), default=0),
                     "kind": kind, "call_id": last.id})
    all_rows = rows
    rows = [r for r in rows if tab == "all" or r["kind"] == tab]
    rows.sort(key=lambda r: (r["kind"] != "need", -_aware(datetime.fromisoformat(r["at"].replace("Z", "+00:00"))).timestamp()))
    pend_calls = [c for c in _calls(session) if _is_pending(c)]
    today = [c for c in _calls(session) if _days_ago(c.started_at) == 0]
    return {"tab": tab, "rows": rows, "pending_calls": len(pend_calls), "pending_today": sum(1 for c in pend_calls if _days_ago(c.started_at) == 0),
            "pending_older": sum(1 for c in pend_calls if _days_ago(c.started_at) > 0), "people": len(all_rows),
            "today": {"handled": len(today), "orders": sum(1 for c in today if ((c.meta or {}).get("order") or {}).get("items") or c.category == "order")}}


# --- the thread with one person ------------------------------------------------------------

_UNIT = {"kg": "kg", "kgs": "kg", "kilo": "kg", "किलो": "kg", "litre": "l", "liter": "l", "ltr": "l", "l": "l", "लीटर": "l", "piece": "pc", "pcs": "pc", "pc": "pc", "packet": "packet", "packets": "packet", "पैकेट": "packet", "dozen": "dozen", "दर्जन": "dozen"}


def _unit(raw: str) -> str:
    return _UNIT.get((raw or "").strip().lower().rstrip("."), "")


def rate_chip(session: Session, call: Call) -> dict | None:
    """"Total ₹X" for an order, only when every item matches a board price quoted per the same unit. Otherwise nothing is guessed."""
    items = ((call.meta or {}).get("order") or {}).get("items") or []
    if not items:
        return None
    board_items = {i.name.strip().lower(): i for i in board.list_items(session)}
    total, parts = 0.0, []
    for it in items:
        b = board_items.get((it.get("board_name") or "").strip().lower())
        qty = it.get("qty_n")
        if b is None or not isinstance(qty, (int, float)) or qty <= 0:
            return None
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:/|per)\s*([A-Za-zऀ-ॿ]+)", b.price or "")
        if not m or _unit(m.group(2)) != _unit(it.get("unit", "")) or not _unit(m.group(2)):
            return None
        price = float(m.group(1).replace(",", "."))
        total += qty * price
        parts.append(f"{b.name} {qty:g} {it.get('unit', '')} × ₹{price:g}".replace("  ", " "))
    label = f"Total ₹{int(total) if total == int(total) else round(total, 2):,}"
    return {"label": label, "text": f"{label} ({', '.join(parts)})."}


def thread(session: Session, phone: str) -> dict:
    names = _contact_names(session)
    calls = [c for c in _calls(session) if c.caller_number == phone or f"call:{c.id}" == phone]
    if not calls:
        raise ServiceError("No calls from this number.", 404)
    calls.sort(key=lambda c: _aware(c.started_at))
    pend = [c for c in calls if _is_pending(c)]
    last = calls[-1]
    items = []
    for c in calls:
        items.append({"type": "call", "id": c.id, "at": iso(c.started_at), "days_ago": _days_ago(c.started_at), "duration_s": c.duration_s, "summary": c.summary,
                      "points": [a["text"] for a in c.action_items], "done": not _is_pending(c), "importance": c.importance, "ask": (c.meta or {}).get("ask", "")})
    real = last.caller_number
    if real:
        for m in session.scalars(select(WaMessage).where(WaMessage.business_id == tenant.current(), WaMessage.phone == real)):
            items.append({"type": "wa", "id": m.id, "sender": m.sender, "text": m.text, "at": iso(m.created_at), "days_ago": _days_ago(m.created_at)})
    items.sort(key=lambda i: i["at"])
    chips = []
    if pend:
        rc = rate_chip(session, pend[-1])
        if rc:
            chips.append({"label": rc["label"], "text": rc["text"]})
        chips += [{"label": r["label"], "text": r["text"]} for r in ((pend[-1].meta or {}).get("replies") or [])]
    return {"name": _display_name(last, names), "phone": real, "key": phone, "items": items, "pending": [c.id for c in pend], "ask": (pend[-1].meta or {}).get("ask", "") if pend else "",
            "chips": chips, "resolved": any(c.importance == "action" for c in calls) and not pend, "spam": all(c.importance == "ignore" for c in calls), "can_reply": bool(real)}


async def send_message(phone: str, text: str) -> dict:
    """The owner's WhatsApp reply. It is recorded and the person's waiting calls are marked done only if WhatsApp really accepted it."""
    from . import whatsapp

    text = re.sub(r"[ \t]+", " ", (text or "")).strip()
    if not text:
        raise ServiceError("Write a message first.", 422)
    if len(text) > 1000:
        raise ServiceError("That message is too long for WhatsApp (1,000 characters at most).", 422)
    number = service.normalize_phone(phone)

    def load(session: Session):
        return settings_store.get_whatsapp(session, service.SECRET_BOX)

    creds = await run_db(load)
    result = await whatsapp.send_text(creds, number, text)
    if not result["sent"]:
        raise ServiceError(result["error"] or "The message was not sent.", 409)

    def save(session: Session):
        session.add(WaMessage(business_id=tenant.current(), phone=number, sender="owner", text=text, provider_id=result["id"]))
        done = 0
        for c in session.scalars(select(Call).where(Call.business_id == tenant.current(), Call.caller_number == number, Call.importance == "action", Call.reviewed.is_(False))):
            c.reviewed = True
            done += 1
        session.flush()
        return done

    done = await run_db(save)
    return {"sent": True, "marked_done": done}


# --- contacts as the app shows them ----------------------------------------------------------

def known(session: Session) -> dict:
    contacts = list(session.scalars(select(Contact).where(Contact.business_id == tenant.current()).order_by(Contact.name)))
    saved = {c.phone for c in contacts}
    out = lambda c: {"id": c.id, "name": c.name, "phone": c.phone, "always_ring": c.always_ring}  # noqa: E731
    callers, seen = [], set()
    for c in _calls(session, 300):
        if c.caller_number and c.caller_number not in saved and c.caller_number not in seen and c.importance != "ignore":
            seen.add(c.caller_number)
            callers.append({"id": None, "name": c.caller_name or c.caller_number, "phone": c.caller_number, "always_ring": False})
    return {"always": [out(c) for c in contacts if c.always_ring], "customers": [out(c) for c in contacts if not c.always_ring] + callers[:40]}


# --- shop info -------------------------------------------------------------------------------

FACT_LABELS = {"delivery": "Home delivery", "address": "Shop address", "hours": "Timing", "rules": "Rules"}
FACT_GROUP = {"delivery": "delivery", "address": "shop", "hours": "shop", "rules": "shop"}


def _age_hours(dt: datetime | None) -> int:
    return 10**6 if dt is None else max(0, int((utcnow() - _aware(dt)).total_seconds() // 3600))


def shop(session: Session) -> dict:
    profile = service.get_profile(session)
    days = config.get_knowledge(session)["stale_days"]
    rates = []
    for i in board.list_items(session):
        age = _age_hours(board._confirmed(i))
        rates.append({"id": i.id, "name": i.name, "price": i.price, "status": i.status, "age_hours": age, "stale": board.is_stale(i, days)})
    facts = []
    conf = profile.get("confirmed") or {}
    for field in ("delivery", "address", "hours", "rules"):
        text = (profile.get(field) or "").strip()
        if not text:
            continue
        at = datetime.fromisoformat(conf[field].replace("Z", "+00:00")) if conf.get(field) else None
        age = _age_hours(at)
        facts.append({"id": f"fact:{field}", "field": field, "group": FACT_GROUP[field], "name": FACT_LABELS[field], "text": text, "age_hours": age, "stale": age >= STALE_FACT_HOURS})
    return {"rates": rates, "facts": facts, "stale": sum(1 for r in rates if r["stale"]) + sum(1 for f in facts if f["stale"]), "stale_days": days}


def confirm(session: Session, item_id: str) -> dict:
    if item_id.startswith("fact:"):
        field = item_id.split(":", 1)[1]
        if field not in FACT_LABELS:
            raise ServiceError("Unknown item.", 404)
        profile = service.get_profile(session)
        conf = {**(profile.get("confirmed") or {}), field: iso(utcnow())}
        service.save_profile(session, service.ProfileIn(**{**profile, "confirmed": conf}))
    else:
        row = session.get(BoardItem, item_id)
        if row is None or row.business_id != tenant.current():
            raise ServiceError("Item not found", 404)
        row.confirmed_at = utcnow()
        session.flush()
    return shop(session)


UNDERSTAND_PROMPT = """You read a short message from a small shop owner in India (Hindi, English or Hinglish) that updates the shop's information. Reply with ONE JSON object and nothing else:
{"rates": [{"name": item name as written, "price": price with unit if said, like "44/kg" or "170"}], "facts": [{"field": "delivery" | "hours" | "address" | "rules", "text": one short sentence in the owner's language}]}
- Use an item name from BOARD ITEMS when the owner means one of them.
- A closed day, opening time or a time range is "hours". Delivery area, charge or timing is "delivery". Credit, returns or other policies are "rules".
- Use only what the message says. If something is unclear leave it out. Empty lists are fine."""


async def understand(text: str) -> dict:
    """Read a typed or spoken update and show what Munshi understood. Nothing is saved until the owner says it is right."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        raise ServiceError("Say or type what changed.", 422)
    if len(text) > 600:
        raise ServiceError("That is too long. Send a few changes at a time.", 422)

    def names(session: Session):
        return [i.name for i in board.list_items(session)][:80], board.list_items(session)

    board_names, _ = await run_db(names)
    try:
        result = await llm.chat([{"role": "system", "content": UNDERSTAND_PROMPT + "\nBOARD ITEMS: " + (", ".join(board_names) or "(none)")}, {"role": "user", "content": text}], temperature=0, max_tokens=500, retries=1)
        raw = result.reply
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception as exc:  # noqa: BLE001
        raise ServiceError("Munshi could not read that. Try saying it in fewer words.", 502) from exc

    def build(session: Session):
        items = board.list_items(session)
        profile = service.get_profile(session)
        rates, facts = [], []
        for r in (data.get("rates") or [])[:20]:
            name = re.sub(r"\s+", " ", str(r.get("name", ""))).strip()[:120]
            price = board.clean_price(str(r.get("price", ""))) if r.get("price") not in (None, "") else ""
            if not name or not price:
                continue
            m = board.find_existing(name, items)
            rates.append({"name": m.name if m else name, "price": price, "old_price": m.price if m else "", "action": "update" if m else "new"})
        for f in (data.get("facts") or [])[:6]:
            field, body = f.get("field"), re.sub(r"\s+", " ", str(f.get("text", ""))).strip()[:300]
            if field in FACT_LABELS and body:
                facts.append({"field": field, "label": FACT_LABELS[field], "text": body, "old": (profile.get(field) or "")})
        return {"from": text, "rates": rates, "facts": facts}

    out = await run_db(build)
    if not out["rates"] and not out["facts"]:
        raise ServiceError("Munshi could not find a rate or shop detail in that. Try, for example: “atta 44” or “closed on Sunday”.", 422)
    return out


def apply(session: Session, rates: list[dict], facts: list[dict]) -> dict:
    added = board.apply_items(session, [{"name": r["name"], "price": r["price"], "status": "in_stock"} for r in rates]) if rates else {"added": 0, "updated": 0}
    profile = service.get_profile(session)
    changed = False
    for f in facts:
        field, text = f.get("field"), (f.get("text") or "").strip()
        if field not in FACT_LABELS or not text:
            continue
        old = (profile.get(field) or "").strip()
        profile[field] = (f"{old}\n{text}" if old and field == "rules" and text not in old else text)
        changed = True
    if changed:
        service.save_profile(session, service.ProfileIn(**profile))
    config.audit(session, "board", f"Shop info updated: {added['added']} rates added, {added['updated']} updated, {len(facts)} details")
    return {**added, "facts": len(facts), "shop": shop(session)}


# --- plan ------------------------------------------------------------------------------------

def plan(session: Session) -> dict:
    biz = tenant.business(session)
    saved = tenant.get(session, "plan", {}) or {}
    start = _aware(biz.created_at)
    end = start + timedelta(days=TRIAL_DAYS)
    left = max(0, -(-int((end - utcnow()).total_seconds()) // 86400))
    month = config.month_start()
    used = len([c for c in _calls(session, 2000) if _aware(c.started_at) >= _aware(month)])
    return {"status": "cancelled" if saved.get("cancelled") else ("trial" if left > 0 else "trial_over"), "trial_days": TRIAL_DAYS, "days_left": left, "ends_on": iso(end),
            "calls_used": used, "call_limit": CALL_LIMIT, "upi": saved.get("upi", ""), "billing_live": False, "receipts": []}


def plan_update(session: Session, *, upi: str | None = None, cancelled: bool | None = None) -> dict:
    saved = dict(tenant.get(session, "plan", {}) or {})
    if upi is not None:
        upi = upi.strip()
        if upi and not re.fullmatch(r"[\w.\-]{2,}@[A-Za-z][\w.\-]{1,}", upi):
            raise ServiceError("Enter a valid UPI ID, like name@upi.", 422)
        saved["upi"] = upi
    if cancelled is not None:
        saved["cancelled"] = bool(cancelled)
    tenant.put(session, "plan", saved)
    config.audit(session, "business", "Plan: " + ("cancelled" if saved.get("cancelled") else "active") + (", UPI saved" if upi else ""))
    return plan(session)
