"""Who is calling the product API, and for which business.

* Admin: signed in with the platform's access token (or open access in test mode). Works across every business and picks one
  with the ``X-Business`` header.
* Owner: holds a business's private link key (``X-Business-Key``). Sees and changes that one business only.
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select

from lab.models import Business
from lab.runner import run_db
from lab.security import require_auth

from . import tenant


def _owner(session, raw: str) -> str | None:
    from . import auth

    if raw.startswith(auth.SESSION_PREFIX):  # signed in with a phone number
        return auth.by_session(session, raw)
    row = tenant.by_key(session, raw)
    return row.id if row else None


def _admin_scope(session, chosen: str, create_if_empty: bool) -> str | None:
    if chosen:
        if session.get(Business, chosen) is None:
            raise HTTPException(404, "Business not found.")
        return chosen
    first = tenant.first_business_id(session)
    if first or not create_if_empty:
        return first
    row = Business(name="My business", settings={})  # a fresh install starts with one business, so the single-owner flow just works
    session.add(row)
    session.flush()
    return row.id


async def scope(request: Request) -> None:
    """Router-wide dependency: authenticate, then say which business this request works on."""
    key = request.headers.get("x-business-key", "")
    if key:
        biz = await run_db(lambda s: _owner(s, key))
        if not biz:
            raise HTTPException(401, "Your sign-in has ended. Please sign in again.")
        request.state.role = "owner"
        tenant.activate(biz)
        return
    require_auth(request)
    request.state.role = "admin"
    chosen = request.headers.get("x-business", "")
    in_admin_area = "/admin/" in request.url.path or request.url.path.endswith("/admin")
    biz = await run_db(lambda s: _admin_scope(s, chosen, create_if_empty=not in_admin_area))
    tenant.activate(biz)


async def admin_only(request: Request) -> None:
    if getattr(request.state, "role", "") != "admin":
        raise HTTPException(403, "Only the platform admin can do this.")


async def any_member(request: Request) -> None:
    """For shared endpoints on other routers (speech to text, voice samples): an admin token or any business link."""
    key = request.headers.get("x-business-key", "")
    if key:
        if not await run_db(lambda s: _owner(s, key)):
            raise HTTPException(401, "Your sign-in has ended. Please sign in again.")
        return
    require_auth(request)
