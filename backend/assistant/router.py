"""The product's HTTP API, mounted at /api/assistant (behind the same access control as the lab)."""
from __future__ import annotations

import os

import llm
import tts
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab import settings_store
from lab.db import get_session
from lab.models import BoardItem, Call, CallNote, Contact
from lab.runner import run_db
from lab.schemas import Strict
from lab.security import require_auth
from lab.service import ServiceError, get_or_404, iso

from . import board, service, whatsapp

router = APIRouter(dependencies=[Depends(require_auth)])

FORWARDING_CODES = [
    {"when": "I don't answer", "dial": "**61*{n}**20#", "note": "Forwards after about 20 seconds of ringing."},
    {"when": "I'm busy on another call", "dial": "**67*{n}#", "note": ""},
    {"when": "My phone is off or has no signal", "dial": "**62*{n}#", "note": ""},
    {"when": "Always (every call)", "dial": "**21*{n}#", "note": "Use this to test, then switch back."},
    {"when": "Turn all forwarding off", "dial": "##002#", "note": ""},
]


def public_base(request: Request) -> str:
    configured = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}"


def _box(request: Request):
    return request.app.state.lab_secret_box


# --- today ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats(session: Session = Depends(get_session)):
    return service.stats(session)


@router.get("/status")
def get_status(request: Request, session: Session = Depends(get_session)):
    """Everything the Setup page needs to say what is connected and what is missing."""
    box = _box(request)
    settings_store.load_runtime(session, box)
    profile = service.get_profile(session)
    phone = settings_store.phone_status(session, box)
    base = public_base(request)
    engine = tts.active()
    return {
        "ai_ready": bool(llm.configured_providers()), "speech_ready": bool(llm.configured_providers() and any(p in ("groq", "custom") for p in llm.configured_providers())),
        "voice": {"engine": engine, "label": "Your device's voice" if engine == "device" else tts.ENGINES[engine]["label"], "server_voice_ready": any(e["configured"] for e in tts.engine_status())},
        "profile_ready": bool(profile["business_name"] and profile["owner_name"]), "phone": phone, "mode": profile["mode"], "assistant_on": profile["assistant_on"],
        "board": {"items": len(board.list_items(session)), "sold_out": sum(1 for i in board.list_items(session) if i.status == "sold_out")},
        "whatsapp": {**settings_store.whatsapp_status(session, box), "template_body": whatsapp.TEMPLATE_BODY},
        "webhooks": {"answer": f"{base}/telephony/plivo/answer", "hangup": f"{base}/telephony/plivo/hangup", "https": base.startswith("https://")},
        "forwarding": [{**c, "dial": c["dial"].format(n=phone["number"].lstrip("+") if phone["number"] else "<your Plivo number>")} for c in FORWARDING_CODES],
        "can_store_keys": box is not None,
    }


# --- profile and contacts ------------------------------------------------------------

@router.get("/profile")
def get_profile(session: Session = Depends(get_session)):
    return service.get_profile(session)


@router.put("/profile")
def put_profile(body: service.ProfileIn, session: Session = Depends(get_session)):
    return service.save_profile(session, body)


class ContactIn(Strict):
    name: str = Field(default="", max_length=120)
    phone: str = Field(min_length=1, max_length=20)
    always_ring: bool = True
    note: str = Field(default="", max_length=300)


class ContactUpdate(Strict):
    name: str | None = Field(default=None, max_length=120)
    always_ring: bool | None = None
    note: str | None = Field(default=None, max_length=300)


class ImportIn(Strict):
    text: str = Field(min_length=1, max_length=60000)


@router.get("/contacts")
def list_contacts(session: Session = Depends(get_session)):
    return [service.contact_out(c) for c in session.scalars(select(Contact).order_by(Contact.name)).all()]


@router.post("/contacts", status_code=201)
def create_contact(body: ContactIn, session: Session = Depends(get_session)):
    return service.contact_out(service.add_contact(session, body.name, body.phone, body.always_ring, body.note))


@router.post("/contacts/import")
def import_contacts(body: ImportIn, session: Session = Depends(get_session)):
    return service.import_contacts(session, body.text)


@router.put("/contacts/{contact_id}")
def update_contact(contact_id: str, body: ContactUpdate, session: Session = Depends(get_session)):
    c = get_or_404(session, Contact, contact_id, "Contact")
    if body.name is not None:
        c.name = body.name.strip() or c.name
    if body.always_ring is not None:
        c.always_ring = body.always_ring
    if body.note is not None:
        c.note = body.note.strip()
    session.flush()
    return service.contact_out(c)


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: str, session: Session = Depends(get_session)):
    session.delete(get_or_404(session, Contact, contact_id, "Contact"))
    return Response(status_code=204)


# --- today's board -------------------------------------------------------------------

class BoardIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    price: str = Field(default="", max_length=40)
    status: str = Field(default="in_stock", pattern="^(in_stock|sold_out|ask)$")


class BoardUpdate(Strict):
    name: str | None = Field(default=None, max_length=120)
    price: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, pattern="^(in_stock|sold_out|ask)$")


class SayIn(Strict):
    text: str = Field(min_length=1, max_length=2000)


@router.get("/board")
def get_board(session: Session = Depends(get_session)):
    return board.board_out(session)


@router.post("/board", status_code=201)
def create_board_item(body: BoardIn, session: Session = Depends(get_session)):
    return board.item_out(board.add_item(session, body.name, body.price, body.status))


@router.post("/board/import")
def import_board(body: ImportIn, session: Session = Depends(get_session)):
    return board.import_items(session, body.text)


@router.post("/board/say")
def say_to_board(body: SayIn, session: Session = Depends(get_session)):
    """"kaju katli khatam" -> marks it sold out. Anything it cannot place is returned, not guessed."""
    return {**board.say(session, body.text), "board": board.board_out(session)}


@router.put("/board/{item_id}")
def update_board_item(item_id: str, body: BoardUpdate, session: Session = Depends(get_session)):
    item = get_or_404(session, BoardItem, item_id, "Item")
    if body.name is not None and body.name.strip():
        item.name = body.name.strip()
    if body.price is not None:
        item.price = board.clean_price(body.price)
    if body.status is not None:
        item.status = body.status
    session.flush()
    return board.item_out(item)


@router.delete("/board/{item_id}", status_code=204)
def delete_board_item(item_id: str, session: Session = Depends(get_session)):
    session.delete(get_or_404(session, BoardItem, item_id, "Item"))
    return Response(status_code=204)


@router.post("/demo")
def load_demo(session: Session = Depends(get_session)):
    """Fill an empty app with a sample shop so the whole product can be tried in a minute. Never overwrites real details."""
    profile = service.get_profile(session)
    if profile["business_name"] or profile["owner_name"] or board.list_items(session):
        raise ServiceError("Your own details are already here, so the sample was not added.", 409)
    service.save_profile(session, service.ProfileIn(business_name="Sharma Traders", owner_name="Ramesh", about="Wholesale rice and pulses in Indore. Delivery within the city.", hours="Mon to Sat, 9am to 8pm",
                                                    address="12 Siyaganj Market, Indore", languages=["hi", "en"], mode="board", owner_phone=""))
    for name, price, status in board.DEMO_BOARD:
        board.add_item(session, name, price, status)
    return {"profile": service.get_profile(session), "board": board.board_out(session)}


# --- calls ---------------------------------------------------------------------------

class StartCall(Strict):
    caller_number: str = Field(default="", max_length=20)
    caller_name: str = Field(default="", max_length=120)


class TurnIn(Strict):
    content: str = Field(min_length=1, max_length=4000)
    audio_seconds: float = Field(default=0, ge=0, le=300)


class NoteIn(Strict):
    body: str = Field(min_length=1, max_length=2000)


class CallUpdate(Strict):
    reviewed: bool | None = None


class ActionUpdate(Strict):
    done: bool


@router.get("/calls")
def list_calls(importance: str | None = Query(None, pattern="^(action|fyi|ignore)$"), q: str | None = Query(None, max_length=100),
               open_only: bool = False, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0), session: Session = Depends(get_session)):
    return service.list_calls(session, importance=importance, q=q, limit=limit, offset=offset, open_only=open_only)


@router.get("/calls/{call_id}")
def get_call(call_id: str, session: Session = Depends(get_session)):
    return service.call_detail(service.load_call(session, call_id))


@router.post("/calls", status_code=201)
async def start_call(body: StartCall, request: Request):
    """Start a practice call in the browser. The person typing or speaking plays the caller."""
    profile = await run_db(service.get_profile)
    if not profile["assistant_on"]:
        raise ServiceError("The assistant is switched off in Setup.", 409)
    if not llm.configured_providers():
        raise ServiceError("Connect your AI key in Setup first.", 409)
    if not (profile["business_name"] and profile["owner_name"]):
        raise ServiceError("Add your name and your business name in Setup first, so the assistant knows who it answers for.", 409)

    def work(session: Session):
        if profile["mode"] == "reply" and not (service.find_contact(session, body.caller_number) or Contact(always_ring=False)).always_ring:
            return {"reply_only": True, "preview": whatsapp.preview(profile, board.list_items(session)), "routed_to_owner": False, "greeting": "", "call": None}
        call, first = service.start_call(session, source="test", number=body.caller_number, name=body.caller_name)
        return {"routed_to_owner": call.handled_by == "owner", "greeting": first, "call": service.call_detail(service.load_call(session, call.id))}
    return await run_db(work)


@router.post("/calls/{call_id}/turns")
async def call_turn(call_id: str, body: TurnIn):
    return await service.run_turn(call_id, body.content, body.audio_seconds)


@router.post("/calls/{call_id}/end")
async def end_call(call_id: str):
    return await service.finish_call(call_id)


@router.post("/calls/{call_id}/spoken")
async def spoken(call_id: str, chars: int = Query(ge=0, le=20000), engine: str = Query("", max_length=20)):
    await run_db(lambda s: service.note_spoken(s, call_id, chars, engine))
    return Response(status_code=204)


@router.put("/calls/{call_id}")
def update_call(call_id: str, body: CallUpdate, session: Session = Depends(get_session)):
    call = get_or_404(session, Call, call_id, "Call")
    if body.reviewed is not None:
        call.reviewed = body.reviewed
    session.flush()
    return {"id": call.id, "reviewed": call.reviewed}


@router.put("/calls/{call_id}/actions/{action_id}")
def update_action(call_id: str, action_id: str, body: ActionUpdate, session: Session = Depends(get_session)):
    call = get_or_404(session, Call, call_id, "Call")
    items = [dict(a) for a in call.action_items]
    hit = next((a for a in items if a["id"] == action_id), None)
    if hit is None:
        raise ServiceError("Action not found", 404)
    hit["done"] = body.done
    call.action_items = items
    if items and all(a["done"] for a in items):
        call.reviewed = True
    session.flush()
    return {"action_items": items, "reviewed": call.reviewed}


@router.delete("/calls/{call_id}", status_code=204)
def delete_call(call_id: str, session: Session = Depends(get_session)):
    call = get_or_404(session, Call, call_id, "Call")
    session.delete(call)
    return Response(status_code=204)


# --- the owner's notes on a call -----------------------------------------------------

@router.post("/calls/{call_id}/notes", status_code=201)
def add_note(call_id: str, body: NoteIn, session: Session = Depends(get_session)):
    call = service.load_call(session, call_id)
    note = CallNote(call_id=call.id, body=body.body, after_turn=len(call.turns))
    session.add(note)
    session.flush()
    return {"id": note.id, "body": note.body, "after_turn": note.after_turn, "created_at": iso(note.created_at), "updated_at": iso(note.updated_at)}


@router.put("/call-notes/{note_id}")
def edit_note(note_id: str, body: NoteIn, session: Session = Depends(get_session)):
    note = service.edit_note(session, note_id, body.body)
    return {"id": note.id, "body": note.body, "after_turn": note.after_turn, "created_at": iso(note.created_at), "updated_at": iso(note.updated_at)}


@router.delete("/call-notes/{note_id}", status_code=204)
def delete_note(note_id: str, session: Session = Depends(get_session)):
    session.delete(get_or_404(session, CallNote, note_id, "Note"))
    return Response(status_code=204)


# --- the instant WhatsApp reply ------------------------------------------------------

class WhatsAppIn(Strict):
    phone_number_id: str = Field(default="", max_length=25)
    access_token: str = Field(default="", max_length=600)
    template: str = Field(default="", max_length=100)
    language: str = Field(default="", max_length=10)


@router.put("/whatsapp")
async def put_whatsapp(body: WhatsAppIn, request: Request):
    box = _box(request)

    def work(session: Session):
        settings_store.save_whatsapp(session, box, phone_number_id=body.phone_number_id, access_token=body.access_token, template=body.template, language=body.language)
        return settings_store.whatsapp_status(session, box)
    return await run_db(work)


@router.delete("/whatsapp", status_code=204)
async def delete_whatsapp():
    await run_db(settings_store.clear_whatsapp)
    return Response(status_code=204)


@router.post("/whatsapp/test")
async def test_whatsapp(request: Request):
    """Send the real reply to the owner's own number, so they see exactly what a caller would."""
    box = _box(request)

    def load(session: Session):
        return settings_store.get_whatsapp(session, box), service.get_profile(session), board.list_items(session)

    creds, profile, items = await run_db(load)
    if not profile["owner_phone"]:
        raise ServiceError("Add your own mobile number in Setup first. The test message goes there.", 409)
    result = await whatsapp.send_reply(creds, profile["owner_phone"], profile, items)
    if not result["sent"]:
        raise ServiceError(result["error"] or "The message could not be sent.", 502)
    return {"sent": True, "to": profile["owner_phone"]}


# --- phone line (Plivo) --------------------------------------------------------------

class PhoneIn(Strict):
    auth_id: str = Field(default="", max_length=60)
    auth_token: str = Field(default="", max_length=200)
    number: str = Field(default="", max_length=20)


@router.put("/phone")
async def put_phone(body: PhoneIn, request: Request):
    box = _box(request)

    def work(session: Session):
        settings_store.save_phone(session, box, auth_id=body.auth_id, auth_token=body.auth_token, number=body.number)
        return settings_store.phone_status(session, box)
    return await run_db(work)


@router.delete("/phone", status_code=204)
async def delete_phone():
    await run_db(settings_store.clear_phone)
    return Response(status_code=204)
