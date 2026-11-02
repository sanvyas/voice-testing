"""Background execution of conversations: generate (simulated caller x assistant), then evaluate.

Concurrency model: a single process runs conversations as asyncio tasks, bounded by a semaphore.
State lives in the database, so progress is visible to the API and survives restarts: on startup,
interrupted work is re-queued (at most MAX_ATTEMPTS times). Run ONE worker process per database.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TypeVar

from sqlalchemy import select, update

import llm
from prompts import build_messages
from . import evaluation, simulator
from .config import Settings
from .db import session_scope
from .models import Conversation, EvalResult, TestRun, Turn, utcnow

logger = logging.getLogger("ai_therapy.lab.runner")
MAX_ATTEMPTS = 3
T = TypeVar("T")


class Cancelled(Exception):
    pass


def _with_session(fn: Callable[..., T], *args: Any) -> T:
    with session_scope() as session:
        return fn(session, *args)


async def run_db(fn: Callable[..., T], *args: Any) -> T:
    """Run a synchronous DB function on a worker thread so the event loop never blocks on I/O."""
    return await asyncio.to_thread(_with_session, fn, *args)


# --- DB steps (each runs in its own short transaction) ----------------------------

def _claim(session, cid: str) -> dict | None:
    """Atomically move queued -> running. Returns what the worker needs, or None if someone else has it."""
    claimed = session.execute(
        update(Conversation)
        .where(Conversation.id == cid, Conversation.status == "queued")
        .values(status="running", started_at=utcnow(), attempts=Conversation.attempts + 1, error=None)
    )
    if claimed.rowcount != 1:
        return None
    conv = session.get(Conversation, cid)
    needs_generation = conv.source == "simulated" and not conv.generated
    if needs_generation:  # restart cleanly; never append to a half-written transcript
        for turn in list(conv.turns):
            session.delete(turn)
    if conv.run_id:
        run = session.get(TestRun, conv.run_id)
        if run and run.status == "queued":
            run.status = "running"
    session.flush()
    return {
        "id": conv.id, "run_id": conv.run_id, "needs_generation": needs_generation, "mood": conv.mood,
        "scenario": conv.scenario_snapshot, "rendered_prompt": conv.rendered_prompt,
        "gen": conv.gen_config or {}, "evalset": conv.evalset_snapshot,
    }


def _is_cancelled(session, cid: str) -> bool:
    conv = session.get(Conversation, cid)
    if conv is None or conv.status == "cancelled":
        return True
    if conv.run_id:
        run = session.get(TestRun, conv.run_id)
        return bool(run and run.cancel_requested)
    return False


def _save_turns(session, cid: str, new_turns: list[dict], provider: str, model: str) -> None:
    for t in new_turns:
        session.add(Turn(conversation_id=cid, idx=t["idx"], role=t["role"], content=t["content"], latency_ms=t.get("latency_ms")))
    conv = session.get(Conversation, cid)
    if provider:
        conv.provider, conv.model = provider, model


def _mark_generated(session, cid: str) -> None:
    session.get(Conversation, cid).generated = True


def _load_turns(session, cid: str) -> list[dict]:
    rows = session.scalars(select(Turn).where(Turn.conversation_id == cid).order_by(Turn.idx)).all()
    return [{"idx": t.idx, "role": t.role, "content": t.content, "latency_ms": t.latency_ms} for t in rows]


def _set_evaluating(session, cid: str) -> None:
    session.get(Conversation, cid).status = "evaluating"


def _save_evaluation(session, cid: str, results, verdict: str, score, reason: str, turns: list[dict]) -> None:
    conv = session.get(Conversation, cid)
    for old in list(conv.results):
        session.delete(old)
    session.flush()
    for r in results:
        session.add(EvalResult(
            conversation_id=cid, position=r.position, param_key=r.key, name=r.name, kind=r.kind, weight=r.weight,
            required=r.required, status=r.status, score=r.score, raw_score=r.raw_score, threshold=r.threshold,
            reasoning=r.reasoning, evidence=r.evidence, details=r.details,
        ))
    latencies = [t["latency_ms"] for t in turns if t["role"] == "assistant" and t.get("latency_ms") is not None]
    conv.verdict, conv.score, conv.verdict_reason = verdict, score, reason
    conv.avg_latency_ms = int(sum(latencies) / len(latencies)) if latencies else None
    conv.status = "completed"
    conv.finished_at = utcnow()


def _fail(session, cid: str, message: str, status: str = "error") -> None:
    conv = session.get(Conversation, cid)
    if conv is None:
        return
    conv.status = status
    conv.error = message[:2000] if status == "error" else None
    conv.verdict = "error" if status == "error" else None
    conv.verdict_reason = message[:500] if status == "error" else "Cancelled before completion."
    conv.finished_at = utcnow()


def refresh_run(session, run_id: str | None) -> None:
    if not run_id:
        return
    run = session.get(TestRun, run_id)
    if run is None:
        return
    pending = session.scalars(
        select(Conversation.id).where(Conversation.run_id == run_id, Conversation.status.in_(("queued", "running", "evaluating"))).limit(1)
    ).first()
    if pending:
        if run.status == "queued":
            run.status = "running"
        return
    run.status = "cancelled" if run.cancel_requested else "completed"
    run.finished_at = utcnow()


# --- the runner -----------------------------------------------------------------

class Runner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._sem = asyncio.Semaphore(settings.max_concurrency)
        self._tasks: set[asyncio.Task] = set()

    def submit(self, conversation_id: str) -> None:
        task = asyncio.create_task(self._guarded(conversation_id), name=f"conv-{conversation_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def recover(self) -> int:
        """Re-queue work interrupted by a restart, then start everything that is queued."""
        def step(session) -> list[str]:
            stuck = session.scalars(select(Conversation).where(Conversation.status.in_(("running", "evaluating")))).all()
            for conv in stuck:
                if conv.attempts >= MAX_ATTEMPTS:
                    _fail(session, conv.id, f"Interrupted by restarts {conv.attempts} times; giving up.")
                else:
                    conv.status = "queued"
            session.flush()
            for conv in stuck:
                refresh_run(session, conv.run_id)
            return list(session.scalars(select(Conversation.id).where(Conversation.status == "queued").order_by(Conversation.created_at)))

        ids = await run_db(step)
        for cid in ids:
            self.submit(cid)
        if ids:
            logger.info("Recovered %d queued conversation(s)", len(ids))
        return len(ids)

    async def _guarded(self, cid: str) -> None:
        async with self._sem:
            run_id = None
            try:
                run_id = await self.execute(cid)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - last line of defence; never lose a conversation silently
                logger.exception("Conversation %s crashed", cid)
                await run_db(_fail, cid, f"Unexpected error: {exc}")
            finally:
                if run_id is None:
                    run_id = await run_db(lambda s: getattr(s.get(Conversation, cid), "run_id", None))
                await run_db(refresh_run, run_id)

    async def execute(self, cid: str) -> str | None:
        ctx = await run_db(_claim, cid)
        if ctx is None:
            return None
        try:
            if ctx["needs_generation"]:
                await self._generate(ctx)
            if await run_db(_is_cancelled, cid):
                raise Cancelled
            await self._evaluate(ctx)
        except Cancelled:
            await run_db(_fail, cid, "", "cancelled")
        except llm.LLMError as exc:
            logger.warning("Conversation %s failed: %s", cid, exc)
            await run_db(_fail, cid, str(exc))
        return ctx["run_id"]

    async def _generate(self, ctx: dict) -> None:
        cid, scenario, gen = ctx["id"], ctx["scenario"], ctx["gen"]
        scripted = scenario.get("scripted_turns") or []
        max_turns = scenario["max_turns"] if not scripted else min(scenario["max_turns"], 1 + len(scripted))
        turns: list[dict] = []
        provider = model = ""
        for n in range(max_turns):
            if await run_db(_is_cancelled, cid):
                raise Cancelled
            if n == 0:
                user_text, ended = scenario["opening_message"], False
            elif scripted:
                user_text, ended = scripted[n - 1], False
            else:
                user_text, ended = await simulator.next_user_message(scenario, turns, self.settings)
                if user_text is None:
                    break
            user_turn = {"idx": len(turns) + 1, "role": "user", "content": user_text}
            prior = [{"role": t["role"], "content": t["content"]} for t in turns]
            reply = await llm.chat(
                build_messages(ctx["rendered_prompt"], prior, user_text),
                provider=gen.get("provider"), model=gen.get("model"),
                temperature=gen.get("temperature", 0.7), max_tokens=gen.get("max_tokens", 350),
            )
            assistant_turn = {"idx": len(turns) + 2, "role": "assistant", "content": reply.reply, "latency_ms": reply.latency_ms}
            provider, model = reply.provider, reply.model
            turns += [user_turn, assistant_turn]
            await run_db(_save_turns, cid, [user_turn, assistant_turn], provider, model)
            if ended:
                break
        await run_db(_mark_generated, cid)

    async def _evaluate(self, ctx: dict) -> None:
        cid = ctx["id"]
        turns = await run_db(_load_turns, cid)
        if not any(t["role"] == "assistant" for t in turns):
            await run_db(_fail, cid, "The conversation has no assistant replies to evaluate.")
            return
        await run_db(_set_evaluating, cid)
        evalset = ctx["evalset"]
        eval_ctx = {"mood": ctx["mood"], "scenario": ctx["scenario"] or None, "rendered_prompt": ctx["rendered_prompt"]}
        results = await evaluation.evaluate(evalset, eval_ctx, turns, self.settings)
        verdict, score, reason = evaluation.compute_verdict(results, float(evalset["pass_threshold"]))
        await run_db(_save_evaluation, cid, results, verdict, score, reason, turns)
        logger.info("Conversation %s verdict=%s score=%s", cid, verdict, score)
