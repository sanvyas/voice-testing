"""Client API for the mobile app (and any web client): /api/v1.

The app never sends a prompt or model settings. It opens a session and the server applies whatever release
(staging or production) the app's API key belongs to, so every client behaves identically.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

import llm
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import release, service, sessions, settings_store
from .db import session_scope
from .models import ApiKey, Conversation, EvalSet, utcnow
from .runner import Runner, run_db
from .schemas import Strict
from .service import ServiceError

MAX_AUDIO_BYTES = 12 * 1024 * 1024
_HITS: dict[str, deque] = defaultdict(deque)


def reset_rate_limits() -> None:
    _HITS.clear()


class AppKey:
    def __init__(self, id: str, environment: str, name: str):
        self.id, self.environment, self.name = id, environment, name


async def require_app_key(request: Request) -> AppKey:
    header = request.headers.get("authorization", "")
    scheme, _, raw = header.partition(" ")
    raw = (raw.strip() if scheme.lower() == "bearer" else "") or request.headers.get("x-api-key", "").strip()
    found = await run_db(lambda s: (lambda k: AppKey(k.id, k.environment, k.name) if k else None)(release.lookup_key(s, raw))) if raw else None
    if found is None:
        raise HTTPException(401, "Invalid or missing API key.", headers={"WWW-Authenticate": "Bearer"})
    limit = request.app.state.lab_settings.app_rate_limit_per_min
    now = time.monotonic()
    hits = _HITS[found.id]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(429, f"Rate limit of {limit} requests per minute reached.", headers={"Retry-After": "10"})
    hits.append(now)
    return found


router = APIRouter(dependencies=[], tags=["client api v1"])


class SessionCreate(Strict):
    client: str = Field(default="", max_length=40, description="e.g. ios, android, web")
    user_ref: str = Field(default="", max_length=100, description="Your own opaque user id (do not send names or emails)")


class TurnIn(Strict):
    text: str = Field(min_length=1, max_length=4000)


class FinishIn(Strict):
    evaluate: bool = True


def _runner(request: Request) -> Runner:
    return request.app.state.lab_runner


@router.get("/config")
async def client_config(key: AppKey = Depends(require_app_key)):
    def work(session: Session):
        dep = release.active(session, key.environment)
        return {
            "environment": key.environment, "ready": dep is not None,
            "release": {"id": dep.id, "prompt": service.prompt_label(dep.prompt_version), "released_at": service.iso(dep.created_at)} if dep else None,
            "history": "full conversation", "max_turns": sessions.MAX_TURNS,
            "speech_to_text": bool(llm.configured_providers() and any(p in ("groq", "custom") for p in llm.configured_providers())),
        }
    return await run_db(work)


@router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, key: AppKey = Depends(require_app_key)):
    def work(session: Session):
        dep = release.active(session, key.environment)
        if dep is None:
            raise ServiceError(f"Nothing has been released to {key.environment} yet. Promote a prompt version in the lab first.", 503)
        conv = Conversation(
            source="app", status="live", title=f"{body.client or 'app'} session", mood="", prompt_version_id=dep.prompt_version_id,
            prompt_label=service.prompt_label(dep.prompt_version), rendered_prompt=release.rendered_for(session, dep), variables=dep.variables,
            gen_config=dep.gen, generated=True, client=body.client, user_ref=body.user_ref, environment=key.environment,
            api_key_id=key.id, deployment_id=dep.id,
        )
        session.add(conv)
        session.flush()
        return {"session_id": conv.id, "environment": key.environment, "release": {"id": dep.id, "prompt": conv.prompt_label}, "created_at": service.iso(conv.created_at)}
    return await run_db(work)


async def _turn(cid: str, text: str, key: AppKey) -> dict:
    ctx = await run_db(lambda s: sessions.prepare_turn(s, cid, sources=("app",), api_key_id=key.id))
    result = await sessions.reply_for(ctx["prompt"], ctx["history"], text, ctx["gen"])
    saved = await run_db(sessions.save_turn, cid, ctx, text, result)
    return {"reply": result.reply, "latency_ms": result.latency_ms, "turn": saved["assistant"]["idx"], "model": result.model}


@router.post("/sessions/{session_id}/turns")
async def send_turn(session_id: str, body: TurnIn, key: AppKey = Depends(require_app_key)):
    return await _turn(session_id, body.text.strip(), key)


async def _read_audio(file: UploadFile) -> bytes:
    audio = await file.read(MAX_AUDIO_BYTES + 1)
    if not audio:
        raise ServiceError("Empty recording", 422)
    if len(audio) > MAX_AUDIO_BYTES:
        raise ServiceError("Recording is too long (limit about 12 MB).", 413)
    return audio


async def _stt(file: UploadFile, language: str):
    audio = await _read_audio(file)
    try:
        return await llm.transcribe(audio, file.filename or "audio.m4a", file.content_type or "", language=language or None)
    except llm.LLMError as exc:
        raise ServiceError(str(exc), 502) from None


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = Form(""), key: AppKey = Depends(require_app_key)):
    result = await _stt(file, language)
    return {"text": result.text, "latency_ms": result.latency_ms}


@router.post("/sessions/{session_id}/audio-turn")
async def audio_turn(session_id: str, file: UploadFile = File(...), language: str = Form(""), key: AppKey = Depends(require_app_key)):
    """Upload a recording; get the transcript and the assistant's reply in one call."""
    await run_db(lambda s: sessions.prepare_turn(s, session_id, sources=("app",), api_key_id=key.id))  # fail fast before paying for STT
    heard = await _stt(file, language)
    if not heard.text:
        return {"transcript": "", "no_speech": True, "reply": None, "stt_latency_ms": heard.latency_ms}
    out = await _turn(session_id, heard.text, key)
    return {"transcript": heard.text, "no_speech": False, "stt_latency_ms": heard.latency_ms, **out}


@router.get("/sessions/{session_id}")
async def get_session_transcript(session_id: str, key: AppKey = Depends(require_app_key)):
    def work(session: Session):
        conv = session.get(Conversation, session_id)
        if conv is None or conv.api_key_id != key.id:
            raise ServiceError("Session not found", 404)
        return {"session_id": conv.id, "status": conv.status, "verdict": conv.verdict, "score": conv.score,
                "turns": [{"turn": t.idx, "role": t.role, "text": t.content, "latency_ms": t.latency_ms} for t in conv.turns]}
    return await run_db(work)


@router.post("/sessions/{session_id}/finish")
async def finish_session(session_id: str, request: Request, body: FinishIn | None = None, key: AppKey = Depends(require_app_key)):
    want_eval = True if body is None else body.evaluate

    def work(session: Session):
        conv = session.get(Conversation, session_id)
        if conv is None or conv.api_key_id != key.id:
            raise ServiceError("Session not found", 404)
        if conv.status != "live":
            return {"session_id": conv.id, "status": conv.status, "evaluating": conv.status in service.PENDING_STATES}
        eval_id = (settings_store.get(session, "app", {}) or {}).get("eval_set_id")
        evalset = None
        if want_eval and eval_id:
            from sqlalchemy.orm import selectinload
            evalset = session.scalars(select(EvalSet).options(selectinload(EvalSet.params)).where(EvalSet.id == eval_id)).first()
        has_reply = any(t.role == "assistant" for t in conv.turns)
        if evalset and has_reply:
            conv.eval_set_id, conv.evalset_snapshot, conv.status = evalset.id, service.snapshot_evalset(evalset), "queued"
        else:
            conv.status, conv.finished_at = "completed", utcnow()
        session.flush()
        return {"session_id": conv.id, "status": conv.status, "evaluating": conv.status == "queued"}

    out = await run_db(work)
    if out["evaluating"]:
        _runner(request).submit(session_id)
    return out


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, key: AppKey = Depends(require_app_key)):
    """Erase a conversation, e.g. when the user asks for their data to be deleted."""
    def work(session: Session):
        conv = session.get(Conversation, session_id)
        if conv is None or conv.api_key_id != key.id:
            raise ServiceError("Session not found", 404)
        if conv.status in service.PENDING_STATES:
            raise ServiceError("Evaluation is still running; try again in a moment.", 409)
        session.delete(conv)
    await run_db(work)
    return Response(status_code=204)
