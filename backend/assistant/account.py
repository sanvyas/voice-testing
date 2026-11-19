"""The owner's own data: download it, or delete the account and everything in it."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from lab.models import AuditEntry, BoardItem, Business, Call, Contact, OwnerSession, WaMessage, utcnow
from lab.service import iso

from . import config, legal, service, tenant


def export(session: Session) -> dict:
    """Everything held about this business, readable. Secrets (keys for outside services) are not included."""
    b = tenant.business(session)
    calls = []
    for c in session.scalars(select(Call).where(Call.business_id == b.id).order_by(Call.started_at)):
        calls.append({"started_at": iso(c.started_at), "caller_number": c.caller_number, "caller_name": c.caller_name, "importance": c.importance, "category": c.category, "summary": c.summary, "language": c.language,
                      "duration_s": c.duration_s, "action_items": c.action_items, "turns": [{"role": t.role, "text": t.content} for t in c.turns], "notes": [{"at": iso(n.created_at), "text": n.body} for n in c.notes]})
    return {
        "exported_at": iso(utcnow()), "policy_version": legal.VERSION, "business": {"id": b.id, "name": b.name, "sign_in_number": b.owner_phone, "created_at": iso(b.created_at)},
        "profile": service.get_profile(session), "consent": (b.settings or {}).get("legal"),
        "contacts": [{"name": c.name, "phone": c.phone, "always_ring": c.always_ring, "note": c.note} for c in session.scalars(select(Contact).where(Contact.business_id == b.id))],
        "rates": [{"name": i.name, "price": i.price, "status": i.status} for i in session.scalars(select(BoardItem).where(BoardItem.business_id == b.id))],
        "messages": [{"at": iso(m.created_at), "phone": m.phone, "from": m.sender, "text": m.text} for m in session.scalars(select(WaMessage).where(WaMessage.business_id == b.id).order_by(WaMessage.created_at))],
        "calls": calls,
    }


def delete_account(session: Session) -> None:
    b = tenant.business(session)
    bid, name = b.id, b.name
    for model in (OwnerSession, WaMessage, Contact, BoardItem):
        session.execute(delete(model).where(model.business_id == bid))
    session.execute(delete(AuditEntry).where(AuditEntry.business_id == bid))
    for c in list(session.scalars(select(Call).where(Call.business_id == bid))):
        session.delete(c)
    session.flush()
    session.delete(session.get(Business, bid))
    config.audit(session, "business", "An account was deleted by its owner", business_id=None)
