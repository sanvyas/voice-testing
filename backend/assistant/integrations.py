"""One place to see every connection, whether it works, and to test it with one tap."""
from __future__ import annotations

import os
import time

import httpx
import llm
import tts
from sqlalchemy.orm import Session

from lab import settings_store
from lab.service import ServiceError, iso
from lab.models import utcnow

from . import vision

CHECKS_KEY = "assistant.checks"


def whatsapp_enabled() -> bool:
    return os.getenv("MUNSHI_WHATSAPP", "off").strip().lower() not in {"off", "0", "false", "no"}


def _checks(session: Session) -> dict:
    return settings_store.get(session, CHECKS_KEY, {}) or {}


def _remember(session: Session, id_: str, ok: bool, message: str) -> dict:
    rec = {"ok": ok, "message": message[:300], "at": iso(utcnow())}
    settings_store.put(session, CHECKS_KEY, {**_checks(session), id_: rec})
    return rec


def overview(session: Session, box, db_info: dict) -> list[dict]:
    settings_store.load_runtime(session, box)
    providers = {p["id"]: p for p in settings_store.provider_status(session, box)}
    groq = providers["groq"]
    custom = providers["custom"]
    phone = settings_store.phone_status(session, box)
    wa = settings_store.whatsapp_status(session, box)
    voices = {e["id"]: e for e in tts.engine_status()}
    used = settings_store.tts_usage(session)
    v_provider, v_model = vision.which()
    v_ok = (groq["configured"] if v_provider == "groq" else custom["configured"])
    checks = _checks(session)
    out = [
        {"id": "ai", "name": "AI (thinking and summaries)", "what": "Talks to callers and writes the call notes.", "connected": groq["configured"], "detail": f"Groq · {groq['model']}" if groq["configured"] else "Not connected", "can_test": True},
        {"id": "speech", "name": "Understanding speech", "what": "Turns the caller's voice into text (Hindi, English and mixes).", "connected": groq["configured"], "detail": "Groq Whisper" if groq["configured"] else "Needs the Groq key", "can_test": True},
        {"id": "vision", "name": "Photo reader", "what": "Reads photos of price lists, shelves and bills.", "connected": v_ok, "detail": f"{v_provider} · {v_model}" if v_ok else f"{v_provider} is not connected", "can_test": True},
        {"id": "voice_google", "name": "Voice: Google", "what": "Speaks to callers in Indian languages.", "connected": voices["google"]["configured"], "detail": f"{used['google']['chars']:,} characters this month" if voices["google"]["configured"] else "No key", "can_test": True},
        {"id": "voice_chatterbox", "name": "Voice: Chatterbox", "what": "Cheaper voice for Hindi and English.", "connected": voices["chatterbox"]["configured"], "detail": f"{used['chatterbox']['chars']:,} characters this month" if voices["chatterbox"]["configured"] else "No key", "can_test": True},
        *(
            [{"id": "whatsapp", "name": "WhatsApp replies", "what": "Sends callers an instant message after a missed call.", "connected": wa["connected"], "detail": f"Number ID {wa['phone_number_id']} · template {wa['template']}" if wa["connected"] else "Not connected", "can_test": True}]
            if whatsapp_enabled() else []
        ),
        {"id": "phone", "name": "Phone line (Plivo)", "what": "Receives the calls your phone forwards.", "connected": phone["connected"], "detail": phone["number"] if phone["connected"] else "Not connected", "can_test": True},
        {"id": "database", "name": "Database", "what": "Where calls, notes, the board and settings are kept.", "connected": True, "detail": db_info["label"], "can_test": False},
    ]
    for item in out:
        item["last_check"] = checks.get(item["id"])
    return out


async def run_test(id_: str, session_fn, box) -> dict:
    """Run one live test. ``session_fn`` runs a function against the database."""
    if id_ == "ai":
        r = await llm.test_provider("groq")
        result = {"ok": r["ok"], "message": r["message"]}
    elif id_ == "speech":
        try:
            stt = (await llm.list_models("groq"))["stt"]
            result = {"ok": bool(stt), "message": f"Whisper models available: {', '.join(stt)}" if stt else "No speech model is available for this key."}
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "message": llm._describe(exc)}
    elif id_ == "vision":
        r = await vision.selftest()
        result = {"ok": r["ok"], "message": r["message"]}
    elif id_ in ("voice_google", "voice_chatterbox"):
        engine = "google" if id_ == "voice_google" else "chatterbox"
        try:
            await session_fn(lambda s: settings_store.tts_check_cap(s, engine, 5))
            speech = await tts.synthesize(engine, "Hello", "en-US")
            await session_fn(lambda s: settings_store.tts_record(s, engine, speech.chars, speech.cost_usd))
            result = {"ok": True, "message": f"Spoke a test word in {speech.latency_ms} ms ({speech.voice})."}
        except (tts.TTSError, ServiceError) as exc:
            result = {"ok": False, "message": getattr(exc, "message", str(exc))}
    elif id_ == "whatsapp":
        creds = await session_fn(lambda s: settings_store.get_whatsapp(s, box))
        if not (creds["access_token"] and creds["phone_number_id"]):
            result = {"ok": False, "message": "WhatsApp is not connected."}
        else:
            try:
                r = await llm.http_client().get(f"https://graph.facebook.com/v21.0/{creds['phone_number_id']}", params={"fields": "display_phone_number,verified_name"}, headers={"Authorization": f"Bearer {creds['access_token']}"})
                data = r.json() if r.content else {}
                result = ({"ok": True, "message": f"Connected: {data.get('verified_name') or 'WhatsApp number'} {data.get('display_phone_number', '')}".strip()} if r.status_code < 400
                          else {"ok": False, "message": f"WhatsApp: {(data.get('error') or {}).get('message', r.reason_phrase)}"})
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "message": f"WhatsApp: {str(exc)[:200]}"}
    elif id_ == "phone":
        creds = await session_fn(lambda s: settings_store.get_phone(s, box))
        if not (creds["auth_token"] and creds["auth_id"]):
            result = {"ok": False, "message": "Add your Plivo Auth ID, Auth Token and number first."}
        else:
            try:
                r = await llm.http_client().get(f"https://api.plivo.com/v1/Account/{creds['auth_id']}/", auth=(creds["auth_id"], creds["auth_token"]))
                result = {"ok": True, "message": "Plivo accepted these credentials."} if r.status_code < 400 else {"ok": False, "message": f"Plivo answered HTTP {r.status_code}: check the Auth ID and Auth Token."}
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "message": f"Plivo: {str(exc)[:200]}"}
    else:
        raise ServiceError("Nothing to test for that one.", 404)
    rec = await session_fn(lambda s: _remember(s, id_, result["ok"], result["message"]))
    return {**result, "at": rec["at"]}
