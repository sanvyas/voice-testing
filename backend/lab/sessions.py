"""One conversation core used by the lab's live test, the mobile/web client API and the production chat endpoint,
so every client gets the same prompt, history window, model settings and therefore the same behaviour."""
from __future__ import annotations

import llm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prompts import build_messages  # noqa: F401  (shared by every client)
from . import service
from .models import Conversation, Turn
from .service import ServiceError, get_or_404

MAX_TURNS = 400  # messages per session (200 exchanges)


async def reply_for(system_prompt: str, history: list[dict], text: str, gen: dict) -> llm.LLMResult:
    try:
        return await llm.chat(
            build_messages(system_prompt, history, text), provider=gen.get("provider") or None, model=gen.get("model") or None,
            temperature=gen.get("temperature", 0.7), max_tokens=gen.get("max_tokens", 350),
        )
    except llm.LLMError as exc:
        raise ServiceError(str(exc), 502) from None


def prepare_turn(session: Session, cid: str, *, sources: tuple[str, ...], api_key_id: str | None = None) -> dict:
    conv = get_or_404(session, Conversation, cid, "Session")
    if conv.source not in sources or conv.status != "live" or (api_key_id is not None and conv.api_key_id != api_key_id):
        # same message for "wrong owner" and "doesn't exist" so ids can't be probed
        raise ServiceError("Session not found or already closed", 404 if api_key_id is not None else 409)
    turns = session.scalars(select(Turn).where(Turn.conversation_id == cid).order_by(Turn.idx)).all()
    if len(turns) >= MAX_TURNS:
        raise ServiceError(f"Session limit reached ({MAX_TURNS} turns). Finish this session and start a new one.", 409)
    return {"prompt": conv.rendered_prompt, "gen": conv.gen_config or {},
            "history": [{"role": t.role, "content": t.content} for t in turns], "next_idx": len(turns) + 1}


def save_turn(session: Session, cid: str, ctx: dict, text: str, result: llm.LLMResult) -> dict:
    conv = get_or_404(session, Conversation, cid, "Session")
    if conv.status != "live":
        raise ServiceError("Session already closed", 409)
    user = Turn(conversation_id=cid, idx=ctx["next_idx"], role="user", content=text)
    bot = Turn(conversation_id=cid, idx=ctx["next_idx"] + 1, role="assistant", content=result.reply, latency_ms=result.latency_ms)
    session.add_all([user, bot])
    conv.provider, conv.model = result.provider, result.model
    try:
        session.flush()
    except IntegrityError:
        raise ServiceError("Another turn was submitted at the same time. Wait for the reply and retry.", 409) from None
    return {"user": service.turn_out(user), "assistant": service.turn_out(bot)}
