"""Plivo phone line. Plivo calls these webhooks; we answer with Plivo XML.

Flow of one call (turn based, so expect a short pause after the caller stops speaking):
  /answer  -> greeting, then <Record>
  /turn    -> Plivo posts the recording; we transcribe it, ask the model, speak the reply, then <Record> again
  /hangup  -> Plivo says the call is over; we write the summary
Every request is checked against Plivo's V3 signature using the saved Auth Token.
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from collections import OrderedDict
from datetime import timedelta
from xml.sax.saxutils import escape, quoteattr

import httpx
import llm
import tts
from fastapi import APIRouter, Request, Response
from plivo.utils import validate_v3_signature
from sqlalchemy import func, select

from lab import settings_store
from lab.models import Call, utcnow
from lab.runner import run_db
from lab.service import ServiceError

from . import prompts, service

logger = logging.getLogger("ai_therapy.assistant.phone")
router = APIRouter()

MAX_CALLS_PER_DAY = int(os.getenv("ASSISTANT_MAX_CALLS_PER_DAY", "200"))
MAX_CALLS_PER_CALLER_10MIN = 5
SILENCE_LIMIT = 2  # empty recordings in a row before we hang up
_background: set[asyncio.Task] = set()


# --- short-lived audio that Plivo fetches with <Play> ----------------------------------

class AudioStore:
    def __init__(self, ttl: int = 600, limit: int = 200):
        self.ttl, self.limit, self._items = ttl, limit, OrderedDict()

    def put(self, audio: bytes, mime: str) -> str:
        key = secrets.token_hex(16)
        self._items[key] = (audio, mime, time.monotonic() + self.ttl)
        while len(self._items) > self.limit:
            self._items.popitem(last=False)
        return key

    def get(self, key: str):
        item = self._items.get(key)
        if item and item[2] > time.monotonic():
            return item[0], item[1]
        self._items.pop(key, None)
        return None


audio_store = AudioStore()


# --- helpers ------------------------------------------------------------------------

def xml(*parts: str) -> Response:
    return Response("<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response>" + "".join(parts) + "</Response>", media_type="text/xml")


def base_url(request: Request) -> str:
    from .router import public_base

    return public_base(request)


async def verified_form(request: Request) -> dict | None:
    """The form fields, or None when the request is not genuinely from Plivo."""
    form = {k: str(v) for k, v in (await request.form()).items()}
    box = request.app.state.lab_secret_box
    phone = await run_db(lambda s: settings_store.get_phone(s, box))
    signature, nonce = request.headers.get("x-plivo-signature-v3", ""), request.headers.get("x-plivo-signature-v3-nonce", "")
    if not (phone["auth_token"] and signature and nonce):
        return None
    url = base_url(request) + request.url.path + (f"?{request.url.query}" if request.url.query else "")
    try:
        ok = validate_v3_signature("POST", url, nonce, phone["auth_token"], signature, dict(form))
    except Exception:  # noqa: BLE001 - a malformed signature is simply "not valid"
        ok = False
    return form if ok else None


def forbidden() -> Response:
    return Response("Forbidden", status_code=403)


async def speak_xml(text: str, language: str, request: Request, call_id: str | None = None) -> str:
    """<Play> our own voice when a server voice is set up, else Plivo's built-in <Speak> (English only; Hindi needs Google or Chatterbox)."""
    engine = tts.active()
    if engine in tts.ENGINES and tts.key_for(engine)[0]:
        try:
            await run_db(lambda s: settings_store.tts_check_cap(s, engine, len(tts.clean_text(text))))
            speech = await tts.synthesize(engine, text, language)
            await run_db(lambda s: (settings_store.tts_record(s, engine, speech.chars, speech.cost_usd), call_id and service.note_spoken(s, call_id, speech.chars, engine)))
            return f"<Play>{escape(base_url(request))}/telephony/audio/{audio_store.put(speech.audio, speech.mime)}.mp3</Play>"
        except (tts.TTSError, ServiceError) as exc:
            logger.warning("server voice failed, using Plivo's voice: %s", exc)
    return f"<Speak>{escape(tts.clean_text(text))}</Speak>"


def record_xml(request: Request, call_id: str) -> str:
    action = f"{base_url(request)}/telephony/plivo/turn?call={call_id}"
    return f"<Record action={quoteattr(action)} method=\"POST\" fileFormat=\"mp3\" maxLength=\"25\" timeout=\"3\" playBeep=\"false\" finishOnKey=\"none\" redirect=\"true\"/>"


def _language(profile: dict) -> str:
    return "hi-IN" if (profile.get("languages") or ["en"])[0] == "hi" else "en-IN"


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


# --- webhooks -----------------------------------------------------------------------

@router.post("/telephony/plivo/answer")
async def answer(request: Request):
    form = await verified_form(request)
    if form is None:
        return forbidden()
    uuid, caller, called = form.get("CallUUID", ""), form.get("From", ""), form.get("To", "")

    def open_call(session):
        profile = service.get_profile(session)
        if not profile["assistant_on"]:
            return profile, None, "off"
        since = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today = session.scalar(select(func.count()).select_from(Call).where(Call.source == "phone", Call.started_at >= since)) or 0
        recent = session.scalar(select(func.count()).select_from(Call).where(Call.source == "phone", Call.caller_number == service._try_phone(caller),
                                                                                  Call.started_at >= utcnow() - timedelta(minutes=10))) if caller else 0
        if today >= MAX_CALLS_PER_DAY or (recent or 0) >= MAX_CALLS_PER_CALLER_10MIN:
            return profile, None, "limit"
        existing = session.scalar(select(Call).where(Call.provider_call_id == uuid)) if uuid else None
        if existing is not None:  # Plivo retried the webhook
            return profile, (existing.id, ""), "retry"
        call, first = service.start_call(session, source="phone", number=caller, provider_call_id=uuid or None)
        if call.handled_by == "owner":
            return profile, (call.id, first), "owner"
        if call.status == "done":  # WhatsApp-only mode
            wa = settings_store.get_whatsapp(session, request.app.state.lab_secret_box)
            return profile, (call.id, ""), "reply" if (wa["access_token"] and wa["phone_number_id"] and profile.get("whatsapp_on", True)) else "reply_unsent"
        return profile, (call.id, first), "ok"

    profile, opened, state = await run_db(open_call)
    lang = _language(profile)
    if state in ("off", "limit"):
        say = "The person you are calling is not available right now. Please try again later."
        return xml(await speak_xml(say, "en-IN", request), "<Hangup/>")
    if state in ("reply", "reply_unsent"):
        _spawn(service.send_reply_for_call(opened[0]))
        say = "We could not take your call. We are sending you the details on WhatsApp." if state == "reply" else "We could not take your call. Please try again later."
        return xml(await speak_xml(say, "en-IN", request, opened[0]), "<Hangup/>")
    if state == "owner":
        say = f"{profile['owner_name'] or 'The person you called'} is not available right now. Please try again in a little while."
        return xml(await speak_xml(say, "en-IN", request, opened[0]), "<Hangup/>")
    call_id, first = opened
    if state == "retry":
        return xml(record_xml(request, call_id))
    return xml(await speak_xml(first, lang, request, call_id), record_xml(request, call_id))


async def _download(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("recording URL is not https")
    response = await llm.http_client().get(url, timeout=20, follow_redirects=True)
    response.raise_for_status()
    return response.content


@router.post("/telephony/plivo/turn")
async def turn(request: Request, call: str = ""):
    form = await verified_form(request)
    if form is None:
        return forbidden()

    def context(session):
        row = session.get(Call, call)
        if row is None or row.status != "live":
            return None
        return service.get_profile(session), int((row.meta or {}).get("silent", 0))

    ctx = await run_db(context)
    if ctx is None:
        return xml("<Hangup/>")
    profile, silent = ctx
    lang = _language(profile)

    async def silence():
        def bump(session):
            row = session.get(Call, call)
            meta = dict(row.meta or {})
            meta["silent"] = int(meta.get("silent", 0)) + 1
            row.meta = meta
        await run_db(bump)
        if silent + 1 >= SILENCE_LIMIT:
            return xml(await speak_xml("I could not hear you, so I will end the call. Please call again.", "en-IN", request, call), "<Hangup/>")
        return xml(await speak_xml("Sorry, I could not hear that. Could you say it again?", lang, request, call), record_xml(request, call))

    try:
        audio = await _download(form.get("RecordUrl", ""))
        heard = await llm.transcribe(audio, "speech.mp3", "audio/mpeg", language=None, retries=1) if len(audio) > 1500 else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not transcribe the recording: %s", exc)
        return await silence()
    text = heard.text if heard else ""
    if not text:
        return await silence()
    seconds = float(form.get("RecordingDuration") or 0)
    try:
        result = await service.run_turn(call, text, seconds)
    except ServiceError as exc:
        logger.warning("turn failed: %s", exc.message)
        return xml(await speak_xml("Sorry, I am having trouble. Please call again in a few minutes.", "en-IN", request, call), "<Hangup/>")
    spoken = await speak_xml(result["assistant"]["content"], lang, request, call)
    return xml(spoken, "<Hangup/>" if result["ended"] else record_xml(request, call))


@router.post("/telephony/plivo/hangup")
async def hangup(request: Request):
    form = await verified_form(request)
    if form is None:
        return forbidden()
    uuid = form.get("CallUUID", "")
    seconds = int(float(form.get("Duration") or form.get("BillDuration") or 0))

    def find(session):
        row = session.scalar(select(Call).where(Call.provider_call_id == uuid)) if uuid else None
        return row.id if row else None

    call_id = await run_db(find)
    if call_id:
        _spawn(service.finish_call(call_id, seconds or None))
    return Response(status_code=204)


@router.get("/telephony/audio/{key}.mp3")
async def audio(key: str):
    item = audio_store.get(key)
    if item is None:
        return Response("Not found", status_code=404)
    return Response(item[0], media_type=item[1], headers={"Cache-Control": "no-store"})
