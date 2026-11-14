"""The call assistant's logic: profile, contacts, running a call turn by turn, and summarising it afterwards."""
from __future__ import annotations

import functools
import json
import logging
import re
import uuid
from datetime import timedelta

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

import llm
from lab import settings_store
from lab.models import Call, CallNote, CallTurn, Contact, utcnow
from lab.runner import run_db
from lab.service import ServiceError, get_or_404, iso

from . import board, config, lexicon, prompts, tenant, whatsapp

logger = logging.getLogger("ai_therapy.assistant")

SECRET_BOX = None  # set at startup (lab/app.py) so background work can read saved keys
MAX_TURNS = 60  # caller + assistant messages in one call; a cost and runaway guard
INR_PER_USD = 95.0
DEFAULT_PROFILE = {"business_name": "", "owner_name": "", "about": "", "hours": "", "faq": "", "rules": "", "languages": ["hi", "en"], "owner_phone": "", "assistant_on": True, "address": "", "mode": "message", "whatsapp_on": True}


# --- phone numbers ------------------------------------------------------------------

def normalize_phone(raw: str) -> str:
    """Return E.164. Bare 10-digit numbers are treated as Indian mobiles."""
    text = (raw or "").strip()
    digits = re.sub(r"\D", "", text)
    if text.startswith("+") and 8 <= len(digits) <= 15:
        return "+" + digits
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    if len(digits) == 11 and digits[0] == "0" and digits[1] in "6789":
        return "+91" + digits[1:]
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return "+" + digits
    raise ServiceError(f"“{raw}” is not a valid phone number. Use 10 digits or +country code.", 422)


def _try_phone(raw: str) -> str:
    try:
        return normalize_phone(raw) if raw else ""
    except ServiceError:
        return ""


# --- profile ------------------------------------------------------------------------

class ProfileIn(BaseModel):
    business_name: str = Field(default="", max_length=120)
    owner_name: str = Field(default="", max_length=80)
    about: str = Field(default="", max_length=600)
    hours: str = Field(default="", max_length=200)
    faq: str = Field(default="", max_length=3000)
    rules: str = Field(default="", max_length=600)
    languages: list[str] = Field(default_factory=lambda: ["hi", "en"], max_length=6)
    owner_phone: str = Field(default="", max_length=20)
    assistant_on: bool = True
    address: str = Field(default="", max_length=200)
    mode: str = Field(default="message", pattern="^(reply|message|board)$")  # reply: WhatsApp only | message: take a message | board: answer from Today's board
    whatsapp_on: bool = True

    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @field_validator("languages")
    @classmethod
    def _langs(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if c not in prompts.LANGUAGE_NAMES]
        if bad or not v:
            raise ValueError("Pick one or more of: " + ", ".join(prompts.LANGUAGE_NAMES))
        return list(dict.fromkeys(v))


def get_profile(session: Session) -> dict:
    return {**DEFAULT_PROFILE, **(tenant.get(session, "profile", {}) or {})}


def save_profile(session: Session, body: ProfileIn) -> dict:
    data = body.model_dump()
    data["owner_phone"] = normalize_phone(data["owner_phone"]) if data["owner_phone"] else ""
    tenant.put(session, "profile", data)
    tenant.business(session).name = (data["business_name"] or tenant.business(session).name)[:120]
    return data


# --- contacts -----------------------------------------------------------------------

def contact_out(c: Contact) -> dict:
    return {"id": c.id, "name": c.name, "phone": c.phone, "always_ring": c.always_ring, "note": c.note}


def add_contact(session: Session, name: str, phone: str, always_ring: bool = True, note: str = "") -> Contact:
    number = normalize_phone(phone)
    if session.scalar(select(Contact).where(Contact.business_id == tenant.current(), Contact.phone == number)):
        raise ServiceError(f"{number} is already in your contacts.", 409)
    c = Contact(business_id=tenant.current(), name=name.strip()[:120] or number, phone=number, always_ring=always_ring, note=note.strip()[:300])
    session.add(c)
    session.flush()
    return c


def import_contacts(session: Session, text: str) -> dict:
    """One contact per line: ``Name, 9876543210`` (a bare number also works)."""
    added, skipped = 0, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"[,\t;]", line, maxsplit=1)]
        name, number = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
        if len(parts) == 2 and re.fullmatch(r"[+\d\s()-]{8,}", parts[0]) and re.search(r"[A-Za-z]", parts[1]):  # "9876543210, Ravi" also works
            name, number = parts[1], parts[0]
        try:
            add_contact(session, name, number)
            added += 1
        except ServiceError as exc:
            skipped.append(f"{line}: {exc.message}")
    return {"added": added, "skipped": skipped}


def find_contact(session: Session, number: str) -> Contact | None:
    n = _try_phone(number)
    return session.scalar(select(Contact).where(Contact.business_id == tenant.current(), Contact.phone == n)) if n else None


# --- calls --------------------------------------------------------------------------

def call_summary(c: Call, turns: int | None = None, notes: int | None = None) -> dict:
    return {"id": c.id, "source": c.source, "handled_by": c.handled_by, "status": c.status, "caller_number": c.caller_number, "caller_name": c.caller_name,
            "importance": c.importance, "category": c.category, "summary": c.summary, "reviewed": c.reviewed, "duration_s": c.duration_s,
            "open_actions": sum(1 for a in c.action_items if not a.get("done")), "turn_count": turns, "note_count": notes,
            "started_at": iso(c.started_at), "ended_at": iso(c.ended_at)}


def call_detail(c: Call) -> dict:
    return {**call_summary(c, len(c.turns), len(c.notes)), "action_items": c.action_items, "callback_number": c.callback_number, "language": c.language,
            "summary_error": c.summary_error, "cost": c.cost, "provider_call_id": c.provider_call_id, "whatsapp": (c.meta or {}).get("whatsapp"),
            "turns": [{"idx": t.idx, "role": t.role, "content": t.content, "created_at": iso(t.created_at)} for t in c.turns],
            "notes": [{"id": n.id, "body": n.body, "after_turn": n.after_turn, "created_at": iso(n.created_at), "updated_at": iso(n.updated_at)} for n in c.notes]}


def load_call(session: Session, call_id: str) -> Call:
    call = session.scalars(select(Call).where(Call.id == call_id, Call.business_id == tenant.current()).options(selectinload(Call.turns), selectinload(Call.notes))).first()
    if call is None:
        raise ServiceError("Call not found", 404)
    return call


def start_call(session: Session, *, source: str, number: str = "", name: str = "", provider_call_id: str | None = None) -> tuple[Call, str]:
    """Open a call. Returns (call, what the assistant says first). Contacts marked always-ring are not answered by the AI."""
    profile = get_profile(session)
    n = _try_phone(number)
    contact = find_contact(session, n) if n else None
    call = Call(business_id=tenant.current(), source=source, caller_number=n, caller_name=(contact.name if contact else name.strip()[:120]), contact_id=contact.id if contact else None,
                provider_call_id=provider_call_id, meta={})
    if contact and contact.always_ring:
        call.handled_by, call.status, call.importance, call.ended_at = "owner", "done", "fyi", utcnow()
        call.summary = f"Missed call from {contact.name} (always-ring). The assistant did not answer; the caller heard that you are unavailable."
        session.add(call)
        session.flush()
        return call, ""
    if profile.get("mode") == "reply":  # WhatsApp-only mode: no conversation, the caller gets the instant reply
        call.status, call.importance, call.ended_at = "done", "fyi", utcnow()
        call.summary = "Missed call. The caller was sent an instant reply instead of being answered by the assistant."
        session.add(call)
        session.flush()
        return call, ""
    first = prompts.greeting(profile, config.resolve(session, prompts.greeting_kind(profile)))
    call.turns.append(CallTurn(idx=1, role="assistant", content=first))
    session.add(call)
    session.flush()
    return call, first


def _history(call: Call) -> list[dict]:
    return [{"role": "assistant" if t.role == "assistant" else "user", "content": t.content} for t in call.turns]


def _clean_reply(text: str) -> tuple[str, bool]:
    ended = prompts.END_MARK in text
    text = text.replace(prompts.END_MARK, "")
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if ended and text.endswith(("?", "？")):  # a question needs an answer: never hang up on it
        ended = False
    return text, ended


def _scoped(fn):
    """Run a call-level job for the business that owns the call (phone webhooks and the sweep have no request scope of their own)."""
    @functools.wraps(fn)
    async def wrapper(call_id: str, *args, **kwargs):
        biz = await run_db(lambda s: tenant.for_call(s, call_id))
        with tenant.acting_as(biz):
            return await fn(call_id, *args, **kwargs)
    return wrapper


@_scoped
async def run_turn(call_id: str, said: str, audio_seconds: float = 0.0) -> dict:
    """One exchange: the caller said something, the assistant answers. Nothing is saved if the model fails."""
    said = re.sub(r"\s+", " ", said or "").strip()
    if not said:
        raise ServiceError("Nothing was said.", 422)
    if len(said) > 2000:
        said = said[:2000]

    def prepare(session: Session):
        call = load_call(session, call_id)
        if call.status != "live" or call.handled_by != "assistant":
            raise ServiceError("This call has ended.", 409)
        profile = get_profile(session)
        system = prompts.receptionist_prompt(profile, board.shareable(session), config.resolve(session, "assistant"), caller_name=call.caller_name, caller_number=call.caller_number,
                                             today=utcnow().strftime("%d %B %Y"), local_words=lexicon.local_words_block(lexicon.effective(session)))
        return system, _history(call), len(call.turns)

    system, history, count = await run_db(prepare)
    forced_end = count + 2 >= MAX_TURNS
    from prompts import build_messages  # the same single place every model input is built

    messages = build_messages(system + ("\nThis call has gone on long. Wrap it up now and end this message with " + prompts.END_MARK + "." if forced_end else ""), history, said)
    try:
        result = await llm.chat(messages, temperature=0.6, max_tokens=320, retries=1)
    except llm.LLMError as exc:
        raise ServiceError(str(exc), 502) from None
    reply, ended = _clean_reply(result.reply)
    if not reply:
        reply = "Sorry, could you say that once more?"
    ended = ended or forced_end

    def store(session: Session):
        call = load_call(session, call_id)
        if call.status != "live":
            raise ServiceError("This call has ended.", 409)
        idx = len(call.turns)
        call.turns.append(CallTurn(idx=idx + 1, role="caller", content=said))
        call.turns.append(CallTurn(idx=idx + 2, role="assistant", content=reply))
        meta = dict(call.meta or {})
        meta["stt_s"] = round(meta.get("stt_s", 0.0) + max(10.0, audio_seconds), 1) if audio_seconds else meta.get("stt_s", 0.0)
        usage = result.usage or {}
        meta["llm_in"] = meta.get("llm_in", 0) + int(usage.get("prompt_tokens") or 0)
        meta["llm_out"] = meta.get("llm_out", 0) + int(usage.get("completion_tokens") or 0)
        meta["silent"] = 0
        call.meta = meta
        session.flush()
        return idx + 1, idx + 2

    caller_idx, assistant_idx = await run_db(store)
    return {"caller": {"idx": caller_idx, "role": "caller", "content": said}, "assistant": {"idx": assistant_idx, "role": "assistant", "content": reply}, "ended": ended,
            "latency_ms": result.latency_ms}


@_scoped
async def send_reply_for_call(call_id: str) -> dict:
    """Send the instant WhatsApp reply for a call that has no conversation (WhatsApp-only mode) and record how it went."""
    def load(session: Session):
        call = load_call(session, call_id)
        creds = settings_store.get_whatsapp(session, SECRET_BOX)
        return creds, call.caller_number, get_profile(session), board.shareable(session)

    creds, number, profile, items = await run_db(load)
    result = await whatsapp.send_reply(creds, number, profile, items) if profile.get("whatsapp_on", True) else {"sent": False, "error": "Switched off in Setup.", "id": ""}

    def save(session: Session):
        call = load_call(session, call_id)
        call.meta = {**(call.meta or {}), "whatsapp": result}
        call.summary = ("Missed call. The caller was sent an instant WhatsApp reply." if result["sent"] else f"Missed call. No reply could be sent ({result['error'] or 'WhatsApp is not connected'}).")
        call.cost = estimate_cost(call)
    await run_db(save)
    return result


def note_spoken(session: Session, call_id: str, chars: int, engine: str) -> None:
    """Remember how much speech was synthesised, for the cost estimate."""
    call = session.scalar(select(Call).where(Call.id == call_id, Call.business_id == tenant.current()))
    if call:
        meta = dict(call.meta or {})
        meta["tts_chars"] = meta.get("tts_chars", 0) + chars
        meta["tts_engine"] = engine
        call.meta = meta


# --- finishing a call ---------------------------------------------------------------

class Summary(BaseModel):
    summary: str = ""
    caller_name: str = ""
    category: str = "other"
    importance: str = "fyi"
    action_items: list[str] = Field(default_factory=list)
    callback_number: str = ""
    language: str = ""
    unanswered: list[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def _short(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v or "").strip()
        if len(v) <= 160:
            return v
        cut = v[:160]
        end = max(cut.rfind(". "), cut.rfind("; "))
        return (cut[: end + 1] if end > 60 else cut.rsplit(" ", 1)[0] + "…")

    @field_validator("unanswered", mode="before")
    @classmethod
    def _unanswered(cls, v):
        return [re.sub(r"\s+", " ", str(x)).strip()[:60] for x in (v or []) if str(x).strip()][:8] if isinstance(v, list) else []

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        return v if v in prompts.CATEGORIES else "other"

    @field_validator("importance")
    @classmethod
    def _imp(cls, v: str) -> str:
        return v if v in prompts.IMPORTANCE else "fyi"

    @field_validator("action_items", mode="before")
    @classmethod
    def _items(cls, v):
        return [str(x).strip()[:300] for x in (v or []) if str(x).strip()][:10] if isinstance(v, list) else []


def parse_summary(raw: str) -> Summary:
    text = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the model's reply")
    return Summary.model_validate(json.loads(text[start:end + 1]))


def estimate_cost(call: Call) -> dict:
    """Rough rupee cost of one call, from counters kept during it. Telephony is Plivo's published India rate (30-second steps)."""
    from tts import ENGINES

    m = call.meta or {}
    stt = m.get("stt_s", 0.0) / 3600 * 0.04 * INR_PER_USD
    llm_cost = (m.get("llm_in", 0) * 0.075 + m.get("llm_out", 0) * 0.30) / 1e6 * INR_PER_USD  # gpt-oss-20b list price, no cache discount
    price = ENGINES.get(m.get("tts_engine", ""), {}).get("price_per_m", 0.0)
    speech = m.get("tts_chars", 0) * price / 1e6 * INR_PER_USD
    pulses = -(-int(call.duration_s) // 30) if call.source == "phone" and call.duration_s else 0
    phone = pulses * 0.38 / 2
    wa = 0.13 if (m.get("whatsapp") or {}).get("sent") else 0.0  # utility template, India list price as shown by MyOperator (Meta rate card not checked)
    parts = {"speech_to_text": stt, "ai": llm_cost, "voice": speech, "phone": phone, "whatsapp": wa}
    return {**{k: round(v, 3) for k, v in parts.items()}, "total": round(sum(parts.values()), 3), "currency": "INR"}


@_scoped
async def finish_call(call_id: str, duration_s: int | None = None) -> dict:
    """Close a call and write its summary. Safe to call twice; the second call just returns the saved result."""
    def load(session: Session):
        call = load_call(session, call_id)
        if call.status == "done":
            return None
        creds = settings_store.get_whatsapp(session, SECRET_BOX)
        sendable = call.source == "phone" and bool(call.caller_number) and creds["access_token"] and creds["phone_number_id"] and not (call.meta or {}).get("whatsapp")
        profile = get_profile(session)
        system = prompts.summary_system(profile, config.resolve(session, "summary"), utcnow().strftime("%d %B %Y"))
        reply = (creds, call.caller_number, profile, board.shareable(session)) if sendable else (None, None, None, None)
        return _history(call), sum(1 for t in call.turns if t.role == "caller"), reply, system

    data = await run_db(load)
    if data is None:
        return await run_db(lambda s: call_detail(load_call(s, call_id)))
    history, caller_turns, reply_ctx, summary_prompt = data
    wa_result = None
    if reply_ctx[0] and reply_ctx[2].get("whatsapp_on", True):  # the instant WhatsApp reply, once per call
        wa_result = await whatsapp.send_reply(reply_ctx[0], reply_ctx[1], reply_ctx[2], reply_ctx[3])
    summary, error = Summary(), ""
    if caller_turns == 0:
        summary = Summary(summary="The caller hung up without saying anything.", importance="ignore", category="other")
    else:
        transcript = "\n".join(f"{'ASSISTANT' if m['role'] == 'assistant' else 'CALLER'}: {m['content']}" for m in history)
        try:
            result = await llm.chat([{"role": "system", "content": summary_prompt}, {"role": "user", "content": transcript}], temperature=0.1, max_tokens=900, retries=1)
            summary = parse_summary(result.reply)
            if summary.importance == "action" and not summary.action_items:  # the owner must always get something to do
                summary.action_items = [f"Follow up: {summary.summary}"[:300]]
        except Exception as exc:  # noqa: BLE001 - a failed summary must never lose the call
            logger.warning("summary failed for %s: %s", call_id, exc)
            error = f"The AI summary failed ({str(exc)[:120]}). Read the transcript."
            summary = Summary(summary="Summary unavailable. Read the transcript below.", importance="action")

    def save(session: Session):
        call = load_call(session, call_id)
        if call.status == "done":
            return call_detail(call)
        call.status, call.ended_at = "done", utcnow()
        call.duration_s = int(duration_s) if duration_s else max(0, int((call.ended_at - call.started_at.replace(tzinfo=call.ended_at.tzinfo)).total_seconds()))
        call.summary, call.category, call.importance = summary.summary, summary.category, summary.importance
        call.caller_name = call.caller_name or summary.caller_name
        call.action_items = [{"id": uuid.uuid4().hex[:8], "text": t, "done": False} for t in summary.action_items]
        call.callback_number = _try_phone(summary.callback_number) or call.caller_number
        call.language, call.summary_error = summary.language[:20], error
        if wa_result is not None:
            call.meta = {**(call.meta or {}), "whatsapp": wa_result}
        if summary.unanswered:
            call.meta = {**(call.meta or {}), "unanswered": summary.unanswered}
        call.cost = estimate_cost(call)
        session.flush()
        return call_detail(call)

    return await run_db(save)


async def close_stale_calls(max_age_minutes: int = 60) -> int:
    """Close calls nobody ended (closed tab, lost hangup callback). They get their summary like any other call."""
    cutoff = utcnow() - timedelta(minutes=max_age_minutes)

    def find(session: Session):
        return list(session.scalars(select(Call.id).where(Call.status == "live", Call.handled_by == "assistant", Call.started_at < cutoff)))

    ids = await run_db(find)
    for cid in ids:
        try:
            await finish_call(cid)
        except Exception:  # noqa: BLE001 - one bad call must not stop the sweep
            logger.exception("could not close stale call %s", cid)
    return len(ids)


# --- lists and numbers -------------------------------------------------------------

def list_calls(session: Session, *, importance: str | None, q: str | None, limit: int, offset: int, open_only: bool = False) -> dict:
    query = select(Call).where(Call.business_id == tenant.current(), Call.handled_by == "assistant", Call.status == "done")
    if importance:
        query = query.where(Call.importance == importance)
    if open_only:
        query = query.where(Call.importance == "action", Call.reviewed.is_(False))
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(or_(Call.summary.ilike(like, escape="\\"), Call.caller_name.ilike(like, escape="\\"), Call.caller_number.ilike(like, escape="\\")))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.order_by(Call.started_at.desc()).limit(limit).offset(offset)).all()
    ids = [c.id for c in rows]
    tc = dict(session.execute(select(CallTurn.call_id, func.count()).where(CallTurn.call_id.in_(ids)).group_by(CallTurn.call_id)).all()) if ids else {}
    nc = dict(session.execute(select(CallNote.call_id, func.count()).where(CallNote.call_id.in_(ids)).group_by(CallNote.call_id)).all()) if ids else {}
    return {"total": total, "items": [call_summary(c, tc.get(c.id, 0), nc.get(c.id, 0)) for c in rows]}


def stats(session: Session) -> dict:
    now = utcnow()
    since = now - timedelta(days=7)
    done = (Call.business_id == tenant.current(), Call.handled_by == "assistant", Call.status == "done")
    def count(*where):
        return session.scalar(select(func.count()).select_from(Call).where(*done, *where)) or 0
    return {"answered_7d": count(Call.started_at >= since), "needs_action": count(Call.importance == "action", Call.reviewed.is_(False)),
            "not_worth_time_7d": count(Call.importance == "ignore", Call.started_at >= since), "rang_you_7d": session.scalar(select(func.count()).select_from(Call).where(Call.business_id == tenant.current(), Call.handled_by == "owner", Call.started_at >= since)) or 0}


def edit_note(session: Session, note_id: str, body: str) -> CallNote:
    note = get_or_404(session, CallNote, note_id, "Note")
    load_call(session, note.call_id)  # 404 unless the call belongs to this business
    note.body = body
    session.flush()
    return note
