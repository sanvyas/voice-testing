"""Sign in with a phone number: a six-digit code by SMS, then a session that stays on that phone.

* A code works once, for 10 minutes, after at most 5 tries. Only its hash is stored.
* Sending is limited per number (one every 45 seconds, 5 an hour) and per address (20 an hour), so the SMS bill cannot be run up.
* A new number becomes a new business, which then goes through onboarding. A known owner number signs back into that business.
* One demo number signs in without an SMS, into a sample shop, so the product can be tried (MUNSHI_DEMO_LOGIN=off switches it off).
* The session token looks like a private link key to the rest of the API (header ``X-Business-Key: s_...``), so every screen works unchanged.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from fastapi import APIRouter, Request
from pydantic import Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from lab.models import Business, Call, CallTurn, OtpCode, OwnerSession, utcnow
from lab.runner import run_db
from lab.schemas import Strict
from lab.service import ServiceError

from . import alerts, board, config, legal, service, sms, tenant

SESSION_PREFIX = "s_"
CODE_TTL = timedelta(minutes=10)
SESSION_TTL = timedelta(days=90)
COOLDOWN_S = 45
MAX_PER_HOUR = 5
MAX_PER_IP_HOUR = 20
MAX_TRIES = 5
DEMO_PHONE = "+919000000001"
DEMO_CODE = "246810"

router = APIRouter()  # public: this is how a person gets in, so it cannot ask for a login


def demo_enabled() -> bool:
    return os.getenv("MUNSHI_DEMO_LOGIN", "on").strip().lower() not in {"off", "0", "false", "no"}


def _hash(phone: str, code: str) -> str:
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def _aware(dt):
    from datetime import timezone
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def mask(phone: str) -> str:
    return f"{phone[:3]}******{phone[-3:]}" if len(phone) > 7 else phone


def _ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else ""))[:45]


# --- codes ----------------------------------------------------------------------------

def issue_code(session: Session, phone: str, ip: str) -> str | None:
    """Make and store a code. Returns it so it can be sent (None for the demo number, whose code is fixed)."""
    now = utcnow()
    session.execute(delete(OtpCode).where(OtpCode.expires_at < now - timedelta(days=1)))  # old rows are not kept
    recent = list(session.scalars(select(OtpCode).where(OtpCode.phone == phone, OtpCode.created_at > now - timedelta(hours=1)).order_by(OtpCode.created_at.desc())))
    if recent and (now - _aware(recent[0].created_at)).total_seconds() < COOLDOWN_S:
        wait = COOLDOWN_S - int((now - _aware(recent[0].created_at)).total_seconds())
        raise ServiceError(f"Please wait {wait} seconds before asking for another code.", 429)
    if len(recent) >= MAX_PER_HOUR:
        raise ServiceError("Too many codes were asked for this number. Please try again in an hour.", 429)
    if ip and (session.scalar(select(func.count()).select_from(OtpCode).where(OtpCode.ip == ip, OtpCode.created_at > now - timedelta(hours=1))) or 0) >= MAX_PER_IP_HOUR:
        raise ServiceError("Too many codes were asked for from this connection. Please try again later.", 429)
    demo = demo_enabled() and phone == DEMO_PHONE
    code = DEMO_CODE if demo else f"{secrets.randbelow(10**6):06d}"
    session.add(OtpCode(phone=phone, code_hash=_hash(phone, code), ip=ip, created_at=now, expires_at=now + CODE_TTL))
    session.flush()
    return None if demo else code


def check_code(session: Session, phone: str, code: str) -> str | None:
    """None when the code is right (and it is used up), else the reason in words. Wrong tries are counted and saved."""
    now = utcnow()
    row = session.scalar(select(OtpCode).where(OtpCode.phone == phone, OtpCode.used.is_(False)).order_by(OtpCode.created_at.desc()))
    if row is None or _aware(row.expires_at) < now:
        return "That code has expired. Ask for a new one."
    if row.attempts >= MAX_TRIES:
        return "Too many wrong tries. Ask for a new code."
    if not hmac.compare_digest(row.code_hash, _hash(phone, code.strip())):
        row.attempts += 1
        session.flush()
        return "That code is not right. Check the SMS and try again."
    row.used = True
    return None


# --- business and session -------------------------------------------------------------

def _sample_calls(session: Session, biz: Business) -> None:
    """Two calls so the demo shop is not empty: an order that needs the owner, and a sales call that does not."""
    now = utcnow()
    rows = [
        ("+919811100011", "Sunil Gupta", "action", "order", "Sunil wants 10 kg atta and 5 kg sugar, delivery tomorrow morning.", 2,
         [("assistant", "नमस्ते, मैं Munshi हूँ, डेमो किराना का AI सहायक। बताइए?"), ("caller", "मुझे 10 किलो आटा और 5 किलो चीनी चाहिए, कल सुबह घर पर।"), ("assistant", "ठीक है, 10 किलो आटा और 5 किलो चीनी, कल सुबह डिलीवरी। आपका नाम बताइए?"), ("caller", "सुनील गुप्ता।"), ("assistant", "ठीक है सुनील जी। रेट और समय के लिए रमेश जी आपको कॉल करेंगे। धन्यवाद।")]),
        ("+919822200022", "", "ignore", "other", "A loan offer. No need to call back.", 26,
         [("assistant", "नमस्ते, मैं Munshi हूँ, डेमो किराना का AI सहायक। बताइए?"), ("caller", "Sir, aapko pre-approved personal loan mil sakta hai."), ("assistant", "जी, रमेश जी को बता दिया जाएगा। धन्यवाद।")]),
    ]
    for phone, name, importance, category, summary, hours_ago, turns in rows:
        started = now - timedelta(hours=hours_ago)
        call = Call(business_id=biz.id, source="phone", status="done", caller_number=phone, caller_name=name, importance=importance, category=category, summary=summary, language="Hindi",
                    duration_s=38, started_at=started, ended_at=started + timedelta(seconds=38), meta={"sample": True},
                    action_items=[{"id": secrets.token_hex(4), "text": "Call Sunil with the rate and delivery time", "done": False}] if importance == "action" else [])
        session.add(call)
        session.flush()
        for i, (role, text) in enumerate(turns, 1):
            session.add(CallTurn(call_id=call.id, idx=i, role=role, content=text))


def demo_business(session: Session) -> Business:
    biz = session.scalar(select(Business).where(Business.owner_phone == DEMO_PHONE))
    if biz is not None:
        return biz
    biz = Business(name="Demo Kirana", owner_phone=DEMO_PHONE, settings={})
    session.add(biz)
    session.flush()
    with tenant.acting_as(biz.id):
        service.save_profile(session, service.ProfileIn(business_name="Demo Kirana", owner_name="Ramesh", about="A neighbourhood grocery store.", hours="every day, 8 am to 9 pm", address="21, Main Bazaar, Nehru Nagar",
                                                        languages=["hi", "en"], mode="board", owner_phone=DEMO_PHONE, open="08:00", close="21:00", delivery="Within 3 km. Free above Rs 500.", rules="No credit is given.", onboarded=True))
        for name, price, status in board.DEMO_BOARD:
            board.add_item(session, name, price, status)
        _sample_calls(session, biz)
    config.audit(session, "system", "Demo shop created for the demo sign-in", business_id=biz.id)
    return biz


def sign_in(session: Session, phone: str, device: str, accept: bool) -> dict:
    """The code was right: find or make the business and start a session."""
    is_new = False
    if demo_enabled() and phone == DEMO_PHONE:
        biz = demo_business(session)
    else:
        biz = session.scalar(select(Business).where(Business.owner_phone == phone, Business.active.is_(True)).order_by(Business.created_at))
        if biz is None:
            is_new = True
            biz = Business(name="New business", owner_phone=phone, settings={"profile": {**service.DEFAULT_PROFILE, "owner_phone": phone}})
            session.add(biz)
            session.flush()
            config.audit(session, "business", "A new business signed up with a phone number", business_id=biz.id)
    if accept:
        with tenant.acting_as(biz.id):
            tenant.put(session, "legal", {"accepted_at": utcnow().isoformat(), "version": legal.VERSION})
    token = SESSION_PREFIX + secrets.token_urlsafe(32)
    now = utcnow()
    session.add(OwnerSession(business_id=biz.id, token_hash=tenant.hash_key(token), device=(device or "")[:120], created_at=now, last_seen=now, expires_at=now + SESSION_TTL))
    session.flush()
    return {"token": token, "business_id": biz.id, "is_new": is_new, "demo": demo_enabled() and phone == DEMO_PHONE, "name": biz.name}


def by_session(session: Session, raw: str) -> str | None:
    """The business a session token belongs to, or None (unknown, expired or signed out). Use keeps it alive."""
    if not raw or not raw.startswith(SESSION_PREFIX) or len(raw) > 100:
        return None
    row = session.scalar(select(OwnerSession).where(OwnerSession.token_hash == tenant.hash_key(raw)))
    now = utcnow()
    if row is None or _aware(row.expires_at) < now:
        return None
    if (now - _aware(row.last_seen)) > timedelta(hours=1):
        row.last_seen, row.expires_at = now, now + SESSION_TTL
    return row.business_id


def sign_out(session: Session, raw: str) -> None:
    session.execute(delete(OwnerSession).where(OwnerSession.token_hash == tenant.hash_key(raw)))


# --- endpoints ------------------------------------------------------------------------

class RequestIn(Strict):
    phone: str = Field(min_length=5, max_length=20)


class VerifyIn(Strict):
    phone: str = Field(min_length=5, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    accept: bool = False
    device: str = Field(default="", max_length=120)


@router.get("/config")
async def auth_config():
    return {"demo": {"phone": DEMO_PHONE, "code": DEMO_CODE} if demo_enabled() else None, "sms_ready": sms.configured(), "terms_version": legal.VERSION}


@router.post("/request")
async def request_code(body: RequestIn, request: Request):
    phone = service.normalize_phone(body.phone)
    code = await run_db(lambda s: issue_code(s, phone, _ip(request)))
    if code is not None:
        try:
            await sms.send_otp(phone, code)
        except ServiceError as exc:
            alerts.raise_alert("sms", "Sign-in codes are not being delivered", exc.message, "error")
            await run_db(lambda s: s.execute(delete(OtpCode).where(OtpCode.phone == phone, OtpCode.used.is_(False))))  # the unsent code is of no use, and must not block the next try
            raise
        alerts.clear("sms")
    return {"sent": True, "phone": mask(phone), "cooldown_s": COOLDOWN_S, "demo": code is None}


@router.post("/verify")
async def verify(body: VerifyIn):
    phone = service.normalize_phone(body.phone)

    def work(s: Session):
        problem = check_code(s, phone, body.code)
        return {"problem": problem} if problem else sign_in(s, phone, body.device, body.accept)
    out = await run_db(work)  # committed here, so a wrong try stays counted
    if "problem" in out:
        raise ServiceError(out["problem"], 401)
    return out


@router.post("/logout", status_code=204)
async def logout(request: Request):
    from fastapi import Response
    raw = request.headers.get("x-business-key", "")
    if raw.startswith(SESSION_PREFIX):
        await run_db(lambda s: sign_out(s, raw))
    return Response(status_code=204)
