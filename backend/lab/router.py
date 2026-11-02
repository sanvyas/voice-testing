"""HTTP API for the testing lab, mounted at /api/lab."""
from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

import llm
from . import rules, schemas, service, sessions
from .db import get_session
from .models import Conversation, EvalParam, EvalSet, Prompt, PromptVersion, Scenario, TestRun, Turn, utcnow
from .runner import Runner, refresh_run, run_db
from .security import require_auth
from .service import ServiceError, get_or_404
from .templating import TemplateError, extract_variables, merge_values, render

router = APIRouter(dependencies=[Depends(require_auth)])

MOOD_SUGGESTIONS = ["anxious", "angry", "sad", "overwhelmed", "withdrawn", "skeptical", "grieving", "crisis", "confused", "hopeful"]


def runner_of(request: Request) -> Runner:
    return request.app.state.lab_runner


# --- config ----------------------------------------------------------------------

@router.get("/config")
def get_config(request: Request):
    settings = request.app.state.lab_settings
    providers = [
        {"id": pid, "label": cfg["label"], "configured": pid in llm.configured_providers(), "default_model": cfg["model"]}
        for pid, cfg in llm.provider_configs().items()
    ]
    return {
        "env": settings.env, "auth_required": bool(settings.api_tokens) and not settings.open_access, "open_access": settings.open_access,
        # SQLite inside a container with no mounted disk is wiped on every restart/deploy
        "database": "postgres" if not settings.database_url.startswith("sqlite") else "sqlite",
        "storage": "temporary" if settings.is_production and settings.database_url.startswith("sqlite") and not os.path.ismount("/data") else "database", "providers": providers,
        "judge": dict(zip(("provider", "model"), llm.role("judge"))),
        "simulator": dict(zip(("provider", "model"), llm.role("simulator"))),
        "limits": {"max_conversations_per_run": settings.max_conversations_per_run, "max_concurrency": settings.max_concurrency},
        "rule_types": rules.RULE_TYPES, "mood_suggestions": MOOD_SUGGESTIONS, "history": "full conversation",
        "llm_ready": bool(llm.configured_providers()), "stt_ready": bool(llm.configured_providers() and any(p in ("groq", "custom") for p in llm.configured_providers())),
    }


# --- prompts ---------------------------------------------------------------------

def _prompt_query():
    return select(Prompt).options(selectinload(Prompt.versions))


@router.get("/prompts")
def list_prompts(include_archived: bool = False, session: Session = Depends(get_session)):
    q = _prompt_query().order_by(Prompt.updated_at.desc())
    if not include_archived:
        q = q.where(Prompt.archived.is_(False))
    return [service.prompt_out(p) for p in session.scalars(q)]


@router.post("/prompts", status_code=201)
def create_prompt(body: schemas.PromptCreate, session: Session = Depends(get_session)):
    prompt = Prompt(name=body.name, description=body.description)
    prompt.versions.append(PromptVersion(version=1, content=body.content, variable_defaults=body.variable_defaults, note=body.note))
    session.add(prompt)
    session.flush()
    return service.prompt_out(prompt, versions=True)


@router.post("/prompts/preview")
def preview_prompt(body: schemas.RenderPreview):
    variables = extract_variables(body.content)
    missing = [v for v in variables if v not in body.variables]
    try:
        rendered = render(body.content, body.variables, strict=False)
    except TemplateError as exc:  # pragma: no cover - strict=False cannot raise
        raise ServiceError(str(exc), 422) from None
    return {"variables": variables, "missing": missing, "rendered": rendered}


@router.get("/prompts/{prompt_id}")
def get_prompt(prompt_id: str, session: Session = Depends(get_session)):
    prompt = session.scalars(_prompt_query().where(Prompt.id == prompt_id)).first()
    if prompt is None:
        raise ServiceError("Prompt not found", 404)
    return service.prompt_out(prompt, versions=True)


@router.patch("/prompts/{prompt_id}")
def update_prompt(prompt_id: str, body: schemas.PromptUpdate, session: Session = Depends(get_session)):
    prompt = session.scalars(_prompt_query().where(Prompt.id == prompt_id)).first()
    if prompt is None:
        raise ServiceError("Prompt not found", 404)
    for field in ("name", "description"):
        value = getattr(body, field)
        if value is not None:
            setattr(prompt, field, value)
    session.flush()
    return service.prompt_out(prompt, versions=True)


@router.post("/prompts/{prompt_id}/versions", status_code=201)
def add_version(prompt_id: str, body: schemas.PromptVersionCreate, session: Session = Depends(get_session)):
    prompt = session.scalars(_prompt_query().where(Prompt.id == prompt_id)).first()
    if prompt is None:
        raise ServiceError("Prompt not found", 404)
    next_no = (prompt.versions[0].version if prompt.versions else 0) + 1
    version = PromptVersion(prompt_id=prompt.id, version=next_no, content=body.content,
                            variable_defaults=body.variable_defaults, note=body.note)
    session.add(version)
    prompt.updated_at = utcnow()
    try:
        session.flush()
    except IntegrityError:
        raise ServiceError("Another version was saved at the same moment; reload and try again.", 409) from None
    return service.version_out(version)


@router.delete("/prompts/{prompt_id}", status_code=204)
def archive_prompt(prompt_id: str, session: Session = Depends(get_session)):
    get_or_404(session, Prompt, prompt_id, "Prompt").archived = True
    return Response(status_code=204)


@router.post("/prompts/{prompt_id}/restore")
def restore_prompt(prompt_id: str, session: Session = Depends(get_session)):
    prompt = get_or_404(session, Prompt, prompt_id, "Prompt")
    prompt.archived = False
    session.flush()
    return service.prompt_out(prompt)


# --- scenarios -------------------------------------------------------------------

@router.get("/scenarios")
def list_scenarios(include_archived: bool = False, mood: str | None = None, session: Session = Depends(get_session)):
    q = select(Scenario).order_by(Scenario.mood, Scenario.name)
    if not include_archived:
        q = q.where(Scenario.archived.is_(False))
    if mood:
        q = q.where(Scenario.mood == mood)
    return [service.scenario_out(s) for s in session.scalars(q)]


@router.post("/scenarios", status_code=201)
def create_scenario(body: schemas.ScenarioIn, session: Session = Depends(get_session)):
    scenario = Scenario(**body.model_dump())
    session.add(scenario)
    session.flush()
    return service.scenario_out(scenario)


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, session: Session = Depends(get_session)):
    return service.scenario_out(get_or_404(session, Scenario, scenario_id, "Scenario"))


@router.put("/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, body: schemas.ScenarioIn, session: Session = Depends(get_session)):
    scenario = get_or_404(session, Scenario, scenario_id, "Scenario")
    for key, value in body.model_dump().items():
        setattr(scenario, key, value)
    session.flush()
    return service.scenario_out(scenario)


@router.delete("/scenarios/{scenario_id}", status_code=204)
def archive_scenario(scenario_id: str, session: Session = Depends(get_session)):
    get_or_404(session, Scenario, scenario_id, "Scenario").archived = True
    return Response(status_code=204)


@router.post("/scenarios/{scenario_id}/restore")
def restore_scenario(scenario_id: str, session: Session = Depends(get_session)):
    scenario = get_or_404(session, Scenario, scenario_id, "Scenario")
    scenario.archived = False
    session.flush()
    return service.scenario_out(scenario)


# --- evaluation sets -------------------------------------------------------------

def _evalset_query():
    return select(EvalSet).options(selectinload(EvalSet.params))


def _apply_params(evalset: EvalSet, body: schemas.EvalSetIn) -> None:
    evalset.params.clear()
    for i, p in enumerate(body.params):
        evalset.params.append(EvalParam(position=i, **p.model_dump()))


@router.get("/eval-sets")
def list_eval_sets(include_archived: bool = False, session: Session = Depends(get_session)):
    q = _evalset_query().order_by(EvalSet.updated_at.desc())
    if not include_archived:
        q = q.where(EvalSet.archived.is_(False))
    return [service.evalset_out(e) for e in session.scalars(q)]


@router.post("/eval-sets", status_code=201)
def create_eval_set(body: schemas.EvalSetIn, session: Session = Depends(get_session)):
    evalset = EvalSet(name=body.name, description=body.description, pass_threshold=body.pass_threshold)
    _apply_params(evalset, body)
    session.add(evalset)
    session.flush()
    return service.evalset_out(evalset)


@router.get("/eval-sets/{eval_set_id}")
def get_eval_set(eval_set_id: str, session: Session = Depends(get_session)):
    evalset = session.scalars(_evalset_query().where(EvalSet.id == eval_set_id)).first()
    if evalset is None:
        raise ServiceError("Evaluation set not found", 404)
    return service.evalset_out(evalset)


@router.put("/eval-sets/{eval_set_id}")
def update_eval_set(eval_set_id: str, body: schemas.EvalSetIn, session: Session = Depends(get_session)):
    evalset = session.scalars(_evalset_query().where(EvalSet.id == eval_set_id)).first()
    if evalset is None:
        raise ServiceError("Evaluation set not found", 404)
    evalset.name, evalset.description, evalset.pass_threshold = body.name, body.description, body.pass_threshold
    session.flush()  # clear the old params before inserting same-keyed ones (unique constraint)
    evalset.params.clear()
    session.flush()
    _apply_params(evalset, body)
    session.flush()
    return service.evalset_out(evalset)


@router.delete("/eval-sets/{eval_set_id}", status_code=204)
def archive_eval_set(eval_set_id: str, session: Session = Depends(get_session)):
    get_or_404(session, EvalSet, eval_set_id, "Evaluation set").archived = True
    return Response(status_code=204)


@router.post("/eval-sets/{eval_set_id}/restore")
def restore_eval_set(eval_set_id: str, session: Session = Depends(get_session)):
    evalset = session.scalars(_evalset_query().where(EvalSet.id == eval_set_id)).first()
    if evalset is None:
        raise ServiceError("Evaluation set not found", 404)
    evalset.archived = False
    session.flush()
    return service.evalset_out(evalset)


# --- runs ------------------------------------------------------------------------

@router.post("/runs", status_code=201)
async def create_run(body: schemas.RunCreate, request: Request):
    settings = request.app.state.lab_settings

    def work(session: Session):
        run, ids = service.create_run(session, body, settings)
        return run.id, ids

    run_id, ids = await run_db(work)
    for cid in ids:
        runner_of(request).submit(cid)
    return await run_db(_run_detail, run_id)


@router.get("/runs")
def list_runs(
    limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), status: str | None = None,
    prompt_version_id: str | None = None, session: Session = Depends(get_session),
):
    q = select(TestRun)
    if status:
        q = q.where(TestRun.status == status)
    if prompt_version_id:
        q = q.where(TestRun.prompt_version_id == prompt_version_id)
    total = session.scalar(select(func.count()).select_from(q.subquery()))
    runs = session.scalars(q.order_by(TestRun.created_at.desc()).limit(limit).offset(offset)).all()
    counts = service.run_counts(session, [r.id for r in runs])
    return {"total": total, "items": [service.run_out(r, counts[r.id]) for r in runs]}


def _mood_breakdown(convs: list[Conversation]) -> list[dict]:
    groups: dict[str, list[Conversation]] = defaultdict(list)
    for c in convs:
        groups[c.mood or "(none)"].append(c)
    out = []
    for mood, items in sorted(groups.items()):
        passed = sum(1 for c in items if c.verdict == "pass")
        failed = sum(1 for c in items if c.verdict == "fail")
        scores = [c.score for c in items if c.score is not None]
        out.append({
            "mood": mood, "total": len(items), "passed": passed, "failed": failed,
            "pass_rate": round(100 * passed / (passed + failed), 1) if passed + failed else None,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        })
    return out


def _run_detail(session: Session, run_id: str) -> dict:
    run = get_or_404(session, TestRun, run_id, "Run")
    convs = session.scalars(select(Conversation).where(Conversation.run_id == run_id).order_by(Conversation.created_at, Conversation.title)).all()
    tc = service.turn_counts(session, [c.id for c in convs])
    counts = service.run_counts(session, [run_id])[run_id]
    # parameter pass rates across the run
    by_param: dict[str, dict] = {}
    for c in session.scalars(select(Conversation).where(Conversation.run_id == run_id).options(selectinload(Conversation.results))):
        for r in c.results:
            if r.status == "skipped":
                continue
            d = by_param.setdefault(r.param_key, {"key": r.param_key, "name": r.name, "kind": r.kind, "passed": 0, "failed": 0, "errored": 0})
            d["passed" if r.status == "pass" else "failed" if r.status == "fail" else "errored"] += 1
    out = service.run_out(run, counts)
    out["conversations"] = [service.conversation_summary(c, tc.get(c.id, 0)) for c in convs]
    out["by_mood"] = _mood_breakdown(list(convs))
    out["by_param"] = list(by_param.values())
    return out


@router.get("/runs/compare")
def compare_runs(ids: str = Query(..., description="Comma-separated run ids"), session: Session = Depends(get_session)):
    run_ids = list(dict.fromkeys(i for i in ids.split(",") if i))
    if not 2 <= len(run_ids) <= 6:
        raise ServiceError("Choose between 2 and 6 runs to compare", 422)
    runs = [get_or_404(session, TestRun, rid, "Run") for rid in run_ids]
    counts = service.run_counts(session, run_ids)
    rows: dict[str, dict] = {}
    for rid in run_ids:
        for c in session.scalars(select(Conversation).where(Conversation.run_id == rid)):
            key = c.scenario_id or c.title
            row = rows.setdefault(key, {"scenario": (c.scenario_snapshot or {}).get("name", c.title), "mood": c.mood, "cells": {}})
            cell = row["cells"].setdefault(rid, {"passed": 0, "failed": 0, "errored": 0, "scores": []})
            if c.verdict == "pass":
                cell["passed"] += 1
            elif c.verdict == "fail":
                cell["failed"] += 1
            else:
                cell["errored"] += 1
            if c.score is not None:
                cell["scores"].append(c.score)
    for row in rows.values():
        for cell in row["cells"].values():
            s = cell.pop("scores")
            cell["avg_score"] = round(sum(s) / len(s), 1) if s else None
    return {
        "runs": [service.run_out(r, counts[r.id]) for r in runs],
        "rows": sorted(rows.values(), key=lambda r: (r["mood"], r["scenario"])),
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)):
    return _run_detail(session, run_id)


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    def work(session: Session):
        run = get_or_404(session, TestRun, run_id, "Run")
        if run.status in ("completed", "cancelled"):
            raise ServiceError("This run has already finished", 409)
        run.cancel_requested = True
        for c in session.scalars(select(Conversation).where(Conversation.run_id == run_id, Conversation.status == "queued")):
            c.status, c.verdict_reason, c.finished_at = "cancelled", "Cancelled before completion.", utcnow()
        session.flush()
        refresh_run(session, run_id)
        return _run_detail(session, run_id)

    return await run_db(work)


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str, session: Session = Depends(get_session)):
    run = get_or_404(session, TestRun, run_id, "Run")
    if run.status in ("queued", "running"):
        raise ServiceError("Cancel the run before deleting it", 409)
    session.delete(run)
    return Response(status_code=204)


@router.get("/runs/{run_id}/export.csv")
def export_run(run_id: str, session: Session = Depends(get_session)):
    run = get_or_404(session, TestRun, run_id, "Run")
    return Response(
        service.run_csv(session, run), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="run-{run_id[:8]}.csv"'},
    )


# --- conversations ---------------------------------------------------------------

@router.get("/conversations")
def list_conversations(
    limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
    verdict: str | None = None, mood: str | None = None, source: str | None = None, status: str | None = None,
    run_id: str | None = None, prompt_version_id: str | None = None, q: str | None = Query(None, max_length=100),
    session: Session = Depends(get_session),
):
    query = select(Conversation)
    for column, value in ((Conversation.verdict, verdict), (Conversation.mood, mood), (Conversation.source, source),
                          (Conversation.status, status), (Conversation.run_id, run_id),
                          (Conversation.prompt_version_id, prompt_version_id)):
        if value:
            query = query.where(column == value)
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(or_(Conversation.title.ilike(like, escape="\\"), Conversation.prompt_label.ilike(like, escape="\\")))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.order_by(Conversation.created_at.desc()).limit(limit).offset(offset)).all()
    tc = service.turn_counts(session, [c.id for c in rows])
    return {"total": total, "items": [service.conversation_summary(c, tc.get(c.id, 0)) for c in rows]}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, session: Session = Depends(get_session)):
    conv = session.scalars(
        select(Conversation).where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.turns), selectinload(Conversation.results))
    ).first()
    if conv is None:
        raise ServiceError("Conversation not found", 404)
    return service.conversation_detail(conv)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, session: Session = Depends(get_session)):
    conv = get_or_404(session, Conversation, conversation_id, "Conversation")
    if conv.status in service.PENDING_STATES:
        raise ServiceError("This conversation is still being processed", 409)
    run_id = conv.run_id
    session.delete(conv)
    session.flush()
    refresh_run(session, run_id)
    return Response(status_code=204)


@router.post("/conversations/import", status_code=201)
async def import_conversation(body: schemas.ImportConversation, request: Request):
    cid = await run_db(lambda s: service.create_import(s, body).id)
    runner_of(request).submit(cid)
    return await run_db(_conversation_detail, cid)


def _conversation_detail(session: Session, cid: str) -> dict:
    conv = session.scalars(
        select(Conversation).where(Conversation.id == cid)
        .options(selectinload(Conversation.turns), selectinload(Conversation.results))
    ).first()
    return service.conversation_detail(conv)


@router.post("/conversations/{conversation_id}/reevaluate")
async def reevaluate(conversation_id: str, request: Request, body: schemas.ReevaluateRequest | None = None):
    new_set = body.eval_set_id if body else None

    def work(session: Session):
        conv = get_or_404(session, Conversation, conversation_id, "Conversation")
        if conv.status in service.PENDING_STATES or conv.status == "live":
            raise ServiceError("This conversation is not finished", 409)
        if new_set:
            evalset = session.scalars(_evalset_query().where(EvalSet.id == new_set)).first()
            if evalset is None:
                raise ServiceError("Evaluation set not found", 404)
            conv.eval_set_id, conv.evalset_snapshot = evalset.id, service.snapshot_evalset(evalset)
        if not conv.evalset_snapshot:
            raise ServiceError("Choose an evaluation set", 422)
        for r in list(conv.results):
            session.delete(r)
        conv.status, conv.verdict, conv.score, conv.error, conv.verdict_reason, conv.finished_at = "queued", None, None, None, "", None
        conv.attempts = 0
        if conv.run_id:
            run = session.get(TestRun, conv.run_id)
            run.status, run.finished_at = "running", None
            if new_set:
                run.config = {**run.config, "evalset_name": conv.evalset_snapshot["name"]}
        session.flush()

    await run_db(work)
    runner_of(request).submit(conversation_id)
    return await run_db(_conversation_detail, conversation_id)


# --- live voice sessions ---------------------------------------------------------

@router.post("/live", status_code=201)
async def live_create(body: schemas.LiveCreate):
    cid = await run_db(lambda s: service.create_live(s, body).id)
    return await run_db(_conversation_detail, cid)


@router.post("/live/{conversation_id}/turns")
async def live_turn(conversation_id: str, body: schemas.LiveTurn):
    ctx = await run_db(lambda s: sessions.prepare_turn(s, conversation_id, sources=("live",)))
    result = await sessions.reply_for(ctx["prompt"], ctx["history"], body.content, ctx["gen"])
    return await run_db(sessions.save_turn, conversation_id, ctx, body.content, result)


@router.post("/live/{conversation_id}/finish")
async def live_finish(conversation_id: str, body: schemas.LiveFinish, request: Request):
    def work(session: Session):
        conv = get_or_404(session, Conversation, conversation_id, "Conversation")
        if conv.source != "live" or conv.status != "live":
            raise ServiceError("This session is not open", 409)
        has_reply = session.scalar(select(func.count()).select_from(Turn).where(Turn.conversation_id == conv.id, Turn.role == "assistant"))
        if not has_reply:
            raise ServiceError("Say something first: there is nothing to evaluate yet", 422)
        evalset = session.scalars(_evalset_query().where(EvalSet.id == body.eval_set_id)).first()
        if evalset is None:
            raise ServiceError("Evaluation set not found", 404)
        conv.eval_set_id, conv.evalset_snapshot = evalset.id, service.snapshot_evalset(evalset)
        conv.status = "queued"
        session.flush()

    await run_db(work)
    runner_of(request).submit(conversation_id)
    return await run_db(_conversation_detail, conversation_id)


# --- dashboard stats -------------------------------------------------------------

@router.get("/stats")
def stats(days: int = Query(30, ge=1, le=365), session: Session = Depends(get_session)):
    since = utcnow() - timedelta(days=days)
    convs = session.scalars(
        select(Conversation).where(Conversation.created_at >= since, Conversation.status == "completed").order_by(Conversation.created_at)
    ).all()
    decided = [c for c in convs if c.verdict in ("pass", "fail")]
    passed = sum(1 for c in decided if c.verdict == "pass")

    def group(key):
        buckets: dict[str, list[Conversation]] = defaultdict(list)
        for c in decided:
            buckets[key(c)].append(c)
        rows = []
        for k, items in buckets.items():
            p = sum(1 for c in items if c.verdict == "pass")
            scores = [c.score for c in items if c.score is not None]
            rows.append({"key": k, "total": len(items), "passed": p, "pass_rate": round(100 * p / len(items), 1),
                         "avg_score": round(sum(scores) / len(scores), 1) if scores else None})
        return sorted(rows, key=lambda r: r["key"])

    trend = defaultdict(lambda: [0, 0])
    for c in decided:
        day = service.iso(c.created_at)[:10]
        trend[day][1] += 1
        trend[day][0] += c.verdict == "pass"
    active = session.scalar(select(func.count()).select_from(Conversation).where(Conversation.status.in_(service.PENDING_STATES)))
    return {
        "days": days, "total": len(decided), "passed": passed, "failed": len(decided) - passed,
        "pass_rate": round(100 * passed / len(decided), 1) if decided else None,
        "active": active, "by_mood": group(lambda c: c.mood or "(none)"),
        "by_prompt": group(lambda c: c.prompt_label or "(none)"),
        "trend": [{"day": d, "total": t, "passed": p, "pass_rate": round(100 * p / t, 1)} for d, (p, t) in sorted(trend.items())],
    }
