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

import hindi_speech
import httpx
import llm
import tts
from fastapi import APIRouter, Request, Response
from plivo.utils import validate_v3_signature
from sqlalchemy import func, select

from lab import settings_store
from lab.models import Business, Call, utcnow
from lab.runner import run_db
from lab.service import ServiceError

from . import config, prompts, service, tenant

logger = logging.getLogger("ai_therapy.assistant.phone")
router = APIRouter()

MAX_CALLS_PER_DAY = int(os.getenv("ASSISTANT_MAX_CALLS_PER_DAY", "200"))
MAX_CALLS_PER_CALLER_10MIN = 5
SILENCE_LIMIT = 2  # empty recordings in a row before we hang up
RECORD_SILENCE_S = max(1, min(5, int(os.getenv("PHONE_RECORD_SILENCE_S", "2"))))  # seconds of quiet that end the caller's turn; every second here is added to every reply
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


_PHRASES: "OrderedDict[tuple[str, str, str], tts.Speech]" = OrderedDict()  # greetings and fixed lines repeat on every call, so keep their audio
_PHRASE_MAX_CHARS, _PHRASE_KEEP = 220, 64
_last_tts_ms: dict[str, int] = {}


async def speak_xml(text: str, language: str, request: Request, call_id: str | None = None) -> str:
    """<Play> our own voice when a server voice is set up, else Plivo's built-in <Speak> (English only; Hindi needs Google or Chatterbox)."""
    engine = tts.active()
    language = _voice_language(text, language)
    if engine in tts.ENGINES and tts.key_for(engine)[0]:
        try:
            clean = tts.clean_text(text)
            cache_key = (engine, language, clean)
            speech = _PHRASES.get(cache_key) if len(clean) <= _PHRASE_MAX_CHARS else None
            if speech is not None:
                _PHRASES.move_to_end(cache_key)
                _last_tts_ms[call_id or ""] = 0
            else:
                await run_db(lambda s: settings_store.tts_check_cap(s, engine, len(clean)))
                speech = await tts.synthesize(engine, text, language, phone=True)
                _last_tts_ms[call_id or ""] = speech.latency_ms
                await run_db(lambda s: (settings_store.tts_record(s, engine, speech.chars, speech.cost_usd), call_id and service.note_spoken(s, call_id, speech.chars, engine)))
                if len(clean) <= _PHRASE_MAX_CHARS:
                    _PHRASES[cache_key] = speech
                    while len(_PHRASES) > _PHRASE_KEEP:
                        _PHRASES.popitem(last=False)
            return f"<Play>{escape(base_url(request))}/telephony/audio/{audio_store.put(speech.audio, speech.mime)}.mp3</Play>"
        except (tts.TTSError, ServiceError) as exc:
            logger.warning("server voice failed, using Plivo's voice: %s", exc)
    return f"<Speak>{escape(tts.clean_text(text))}</Speak>"


def _voice_language(text: str, default: str) -> str:
    """Speak with the voice that matches the script of the reply: a Hindi voice reads Devanagari well and English badly, and the reverse."""
    return "hi-IN" if hindi_speech.has_devanagari(text) else ("en-IN" if default.lower().startswith("hi") or default.lower().startswith("en") else default)


def record_xml(request: Request, call_id: str) -> str:
    action = f"{base_url(request)}/telephony/plivo/turn?call={call_id}"
    return f"<Record action={quoteattr(action)} method=\"POST\" fileFormat=\"mp3\" maxLength=\"25\" timeout=\"{RECORD_SILENCE_S}\" playBeep=\"false\" finishOnKey=\"none\" redirect=\"true\"/>"


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

    def which(session):
        row = tenant.by_number(session, called)
        return (row.id, row.active) if row else (None, False)

    biz_id, active = await run_db(which)
    if not biz_id or not active:  # a number nobody owns, or a paused business
        return xml(await speak_xml("The person you are calling is not available right now. Please try again later.", "en-IN", request), "<Hangup/>")
    with tenant.acting_as(biz_id):
        return await _answer(request, uuid, caller, called)


async def _answer(request: Request, uuid: str, caller: str, called: str):
    def open_call(session):
        profile = service.get_profile(session)
        if not profile["assistant_on"]:
            return profile, None, "off"
        since = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        mine = Call.business_id == tenant.current()
        today = session.scalar(select(func.count()).select_from(Call).where(mine, Call.source == "phone", Call.started_at >= since)) or 0
        recent = session.scalar(select(func.count()).select_from(Call).where(mine, Call.source == "phone", Call.caller_number == service._try_phone(caller),
                                                                                  Call.started_at >= utcnow() - timedelta(minutes=10))) if caller else 0
        if today >= MAX_CALLS_PER_DAY or (recent or 0) >= MAX_CALLS_PER_CALLER_10MIN or config.over_budget(session):
            return profile, None, "limit"
        existing = session.scalar(select(Call).where(mine, Call.provider_call_id == uuid)) if uuid else None
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
    biz_id = await run_db(lambda s: s.scalar(select(Call.business_id).where(Call.id == call)))
    if not biz_id:
        return xml("<Hangup/>")
    with tenant.acting_as(biz_id):
        return await _turn(request, call, form)


async def _turn(request: Request, call: str, form: dict):
    def context(session):
        row = session.scalar(select(Call).where(Call.id == call, Call.business_id == tenant.current()))
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
            row = session.scalar(select(Call).where(Call.id == call, Call.business_id == tenant.current()))
            meta = dict(row.meta or {})
            meta["silent"] = int(meta.get("silent", 0)) + 1
            row.meta = meta
        await run_db(bump)
        if silent + 1 >= SILENCE_LIMIT:
            return xml(await speak_xml("I could not hear you, so I will end the call. Please call again.", "en-IN", request, call), "<Hangup/>")
        return xml(await speak_xml("Sorry, I could not hear that. Could you say it again?", lang, request, call), record_xml(request, call))

    t0 = time.perf_counter()
    try:
        audio = await _download(form.get("RecordUrl", ""))
        t_download = time.perf_counter()
        heard = await llm.transcribe(audio, "speech.mp3", "audio/mpeg", language=None, retries=1) if len(audio) > 1500 else None
        t_stt = time.perf_counter()
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
    t_llm = time.perf_counter()
    spoken = await speak_xml(result["assistant"]["content"], lang, request, call)
    t_end = time.perf_counter()
    logger.info("turn timing call=%s download_ms=%d stt_ms=%d model_ms=%d (llm_only=%s) voice_ms=%d (synth=%s) total_ms=%d record_silence_s=%d",
                call, (t_download - t0) * 1000, (t_stt - t_download) * 1000, (t_llm - t_stt) * 1000, result.get("latency_ms"), (t_end - t_llm) * 1000,
                _last_tts_ms.pop(call, None), (t_end - t0) * 1000, RECORD_SILENCE_S)
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
