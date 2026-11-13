"""Which business a request, a phone call or a background job is working for.

Every query on contacts, calls, the board and the audit trail goes through ``current()``, so one business can never read or
change another's data. Platform-wide code (the admin portal) names the business explicitly or works across all of them.
"""
from __future__ import annotations

import hashlib
import secrets
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from lab.models import Business, Call, utcnow
from lab.service import ServiceError

_current: ContextVar[str | None] = ContextVar("munshi_business", default=None)
KEY_PREFIX = "mk_"


def current() -> str:
    biz = _current.get()
    if not biz:
        raise ServiceError("No business is selected.", 409)
    return biz


def active_id() -> str | None:
    return _current.get()


def activate(biz_id: str | None):
    return _current.set(biz_id)


@contextmanager
def acting_as(biz_id: str):
    token = _current.set(biz_id)
    try:
        yield
    finally:
        _current.reset(token)


# --- the business row and its settings ------------------------------------------------

def business(session: Session, biz_id: str | None = None) -> Business:
    row = session.get(Business, biz_id or current())
    if row is None:
        raise ServiceError("Business not found.", 404)
    return row


def get(session: Session, key: str, default=None):
    return (business(session).settings or {}).get(key, default)


def put(session: Session, key: str, value) -> None:
    row = business(session)
    row.settings = {**(row.settings or {}), key: value}  # a new dict, so the JSON column notices the change
    session.flush()


# --- owner links ----------------------------------------------------------------------

def new_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(24)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def by_key(session: Session, raw: str) -> Business | None:
    if not raw or not raw.startswith(KEY_PREFIX) or len(raw) > 100:
        return None
    return session.scalar(select(Business).where(Business.key_hash == hash_key(raw)))


def by_number(session: Session, number: str) -> Business | None:
    """The business a Plivo number belongs to. With a single business and no number set up yet, that one business."""
    from .service import _try_phone

    n = _try_phone(number)
    if n:
        row = session.scalar(select(Business).where(Business.phone_number == n))
        if row:
            return row
    everyone = session.scalars(select(Business).limit(2)).all()
    return everyone[0] if len(everyone) == 1 else None


def for_call(session: Session, call_id: str) -> str:
    """The business to work for when handling a call id. Inside a request that is already scoped, it stays that business."""
    if _current.get():
        return _current.get()
    owner = session.scalar(select(Call.business_id).where(Call.id == call_id))
    if not owner:
        raise ServiceError("Call not found", 404)
    return owner


def first_business_id(session: Session) -> str | None:
    return session.scalar(select(Business.id).order_by(Business.created_at).limit(1))
