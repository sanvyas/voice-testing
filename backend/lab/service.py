"""Business logic shared by the API: serialisation, snapshots, and run/conversation creation."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas
from .config import Settings
from .models import (
    Conversation, EvalParam, EvalSet, Prompt, PromptVersion, Scenario, Setting, TestRun, Turn,
)
from .templating import TemplateError, extract_variables, merge_values, render

PENDING_STATES = ("queued", "running", "evaluating")


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite returns naive datetimes; everything we store is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# --- serialisation ---------------------------------------------------------------

def version_out(v: PromptVersion) -> dict:
    return {
        "id": v.id, "prompt_id": v.prompt_id, "version": v.version, "content": v.content,
        "variable_defaults": v.variable_defaults, "variables": extract_variables(v.content),
        "note": v.note, "created_at": iso(v.created_at),
    }


def prompt_out(p: Prompt, *, versions: bool = False) -> dict:
    latest = p.versions[0] if p.versions else None
    out = {
        "id": p.id, "name": p.name, "description": p.description, "archived": p.archived,
        "created_at": iso(p.created_at), "updated_at": iso(p.updated_at),
        "latest_version": version_out(latest) if latest else None,
        "version_count": len(p.versions),
    }
    if versions:
        out["versions"] = [version_out(v) for v in p.versions]
    return out


def scenario_out(s: Scenario) -> dict:
    return {
        "id": s.id, "name": s.name, "mood": s.mood, "persona": s.persona, "behavior": s.behavior,
        "opening_message": s.opening_message, "intensity": s.intensity, "max_turns": s.max_turns,
        "scripted_turns": s.scripted_turns, "variables": s.variables, "tags": s.tags,
        "archived": s.archived, "created_at": iso(s.created_at), "updated_at": iso(s.updated_at),
    }


def param_out(p: EvalParam) -> dict:
    return {
        "id": p.id, "key": p.key, "name": p.name, "description": p.description, "kind": p.kind,
        "config": p.config, "weight": p.weight, "required": p.required, "applies_to_moods": p.applies_to_moods,
    }


def evalset_out(e: EvalSet) -> dict:
    return {
        "id": e.id, "name": e.name, "description": e.description, "pass_threshold": e.pass_threshold,
        "archived": e.archived, "params": [param_out(p) for p in e.params],
        "created_at": iso(e.created_at), "updated_at": iso(e.updated_at),
    }


def snapshot_scenario(s: Scenario) -> dict:
    return {
        "id": s.id, "name": s.name, "mood": s.mood, "persona": s.persona, "behavior": s.behavior,
        "opening_message": s.opening_message, "intensity": s.intensity, "max_turns": s.max_turns,
        "scripted_turns": list(s.scripted_turns or []), "variables": dict(s.variables or {}),
    }


def snapshot_evalset(e: EvalSet) -> dict:
    return {
        "id": e.id, "name": e.name, "pass_threshold": e.pass_threshold,
        "params": [
            {
                "key": p.key, "name": p.name, "description": p.description, "kind": p.kind, "config": p.config,
                "weight": p.weight, "required": p.required, "applies_to_moods": list(p.applies_to_moods or []),
            }
            for p in e.params
        ],
    }


def result_out(r) -> dict:
    return {
        "key": r.param_key, "name": r.name, "kind": r.kind, "weight": r.weight, "required": r.required,
        "status": r.status, "score": r.score, "raw_score": r.raw_score, "threshold": r.threshold,
        "reasoning": r.reasoning, "evidence": r.evidence, "details": r.details,
    }


def turn_out(t: Turn) -> dict:
    return {"idx": t.idx, "role": t.role, "content": t.content, "latency_ms": t.latency_ms, "created_at": iso(t.created_at)}


def turn_counts(session: Session, ids: Iterable[str]) -> dict[str, int]:
    ids = list(ids)
    if not ids:
        return {}
    rows = session.execute(
        select(Turn.conversation_id, func.count()).where(Turn.conversation_id.in_(ids)).group_by(Turn.conversation_id)
    ).all()
    return {cid: n for cid, n in rows}


def conversation_summary(c: Conversation, turns: int | None = None) -> dict:
    return {
        "id": c.id, "run_id": c.run_id, "source": c.source, "status": c.status, "verdict": c.verdict,
        "score": c.score, "verdict_reason": c.verdict_reason, "error": c.error, "title": c.title,
        "mood": c.mood, "prompt_label": c.prompt_label, "prompt_version_id": c.prompt_version_id,
        "scenario_id": c.scenario_id, "eval_set_id": c.eval_set_id,
        "evalset_name": (c.evalset_snapshot or {}).get("name", ""),
        "provider": c.provider, "model": c.model, "avg_latency_ms": c.avg_latency_ms,
        "turn_count": turns, "created_at": iso(c.created_at), "finished_at": iso(c.finished_at),
        "client": c.client, "environment": c.environment, "user_ref": c.user_ref,
    }


def conversation_detail(c: Conversation) -> dict:
    out = conversation_summary(c, len(c.turns))
    out.update(
        rendered_prompt=c.rendered_prompt, variables=c.variables, scenario=c.scenario_snapshot,
        evalset=c.evalset_snapshot, gen_config=c.gen_config,
        turns=[turn_out(t) for t in c.turns], results=[result_out(r) for r in c.results],
    )
    return out


def run_counts(session: Session, run_ids: list[str]) -> dict[str, dict]:
    counts = {rid: dict(total=0, passed=0, failed=0, errored=0, pending=0, cancelled=0, score_sum=0.0, score_n=0) for rid in run_ids}
    if not run_ids:
        return counts
    rows = session.execute(
        select(Conversation.run_id, Conversation.status, Conversation.verdict, Conversation.score)
        .where(Conversation.run_id.in_(run_ids))
    ).all()
    for rid, status, verdict, score in rows:
        c = counts[rid]
        c["total"] += 1
        if status in PENDING_STATES:
            c["pending"] += 1
        elif status == "cancelled":
            c["cancelled"] += 1
        elif verdict == "pass":
            c["passed"] += 1
        elif verdict == "fail":
            c["failed"] += 1
        else:
            c["errored"] += 1
        if score is not None and status == "completed":
            c["score_sum"] += score
            c["score_n"] += 1
    return counts


def run_out(run: TestRun, counts: dict) -> dict:
    decided = counts["passed"] + counts["failed"]
    return {
        "id": run.id, "name": run.name, "status": run.status, "prompt_version_id": run.prompt_version_id,
        "eval_set_id": run.eval_set_id, "config": run.config, "created_at": iso(run.created_at),
        "finished_at": iso(run.finished_at),
        "prompt_label": (run.config or {}).get("prompt_label", ""),
        "evalset_name": (run.config or {}).get("evalset_name", ""),
        "counts": {k: counts[k] for k in ("total", "passed", "failed", "errored", "pending", "cancelled")},
        "pass_rate": round(100 * counts["passed"] / decided, 1) if decided else None,
        "avg_score": round(counts["score_sum"] / counts["score_n"], 1) if counts["score_n"] else None,
    }


# --- lookups ---------------------------------------------------------------------

def get_or_404(session: Session, model, id_: str, what: str):
    obj = session.get(model, id_)
    if obj is None:
        raise ServiceError(f"{what} not found", 404)
    return obj


def resolve_prompt(session: Session, version_id: str, overrides: dict[str, str]) -> tuple[PromptVersion, dict[str, str], str]:
    version = get_or_404(session, PromptVersion, version_id, "Prompt version")
    used = extract_variables(version.content)
    unknown = set(overrides) - set(used)
    if unknown:
        raise ServiceError("Unknown variables for this prompt: " + ", ".join(sorted(unknown)), 422)
    values = merge_values(version.variable_defaults, overrides)
    try:
        rendered = render(version.content, values)
    except TemplateError as exc:
        raise ServiceError(str(exc), 422) from None
    return version, values, rendered


def prompt_label(version: PromptVersion) -> str:
    return f"{version.prompt.name} v{version.version}"


# --- how the assistant talks: creativity and reply length, one setting for tests, Talk and releases --------

GENERATION_DEFAULTS = {"temperature": 0.7, "max_tokens": 350}


def generation_settings(session: Session) -> dict:
    row = session.get(Setting, "generation")
    stored = (row.value if row else {}) or {}
    return {k: stored.get(k, v) for k, v in GENERATION_DEFAULTS.items()}


def save_generation(session: Session, temperature: float, max_tokens: int) -> dict:
    value = {"temperature": float(temperature), "max_tokens": int(max_tokens)}
    row = session.get(Setting, "generation")
    if row is None:
        session.add(Setting(key="generation", value=value))
    else:
        row.value = value
    session.flush()
    return value


def resolve_generation(session: Session, temperature, max_tokens) -> tuple[float, int]:
    """Explicit request values win; otherwise the saved setting."""
    saved = generation_settings(session)
    return (saved["temperature"] if temperature is None else temperature), (saved["max_tokens"] if max_tokens is None else max_tokens)


# --- creation --------------------------------------------------------------------

def create_run(session: Session, req: schemas.RunCreate, settings: Settings) -> tuple[TestRun, list[str]]:
    total = len(req.scenario_ids) * req.repeats
    if total > settings.max_conversations_per_run:
        raise ServiceError(
            f"This run would create {total} conversations; the limit is {settings.max_conversations_per_run}.", 422
        )
    version, values, rendered = resolve_prompt(session, req.prompt_version_id, req.variables)
    evalset = get_or_404(session, EvalSet, req.eval_set_id, "Evaluation set")
    if not evalset.params:
        raise ServiceError("The evaluation set has no parameters", 422)
    scenarios = []
    for sid in dict.fromkeys(req.scenario_ids):
        scenarios.append(get_or_404(session, Scenario, sid, "Scenario"))
    label = prompt_label(version)
    temperature, max_tokens = resolve_generation(session, req.temperature, req.max_tokens)
    gen = {"temperature": temperature, "max_tokens": max_tokens, "provider": req.provider, "model": req.model}
    run = TestRun(
        name=req.name or f"{label} · {len(scenarios)} scenario{'s' if len(scenarios) != 1 else ''}",
        status="queued", prompt_version_id=version.id, eval_set_id=evalset.id,
        config={**gen, "variables": values, "repeats": req.repeats, "max_turns": req.max_turns,
                "prompt_label": label, "evalset_name": evalset.name, "scenario_ids": [s.id for s in scenarios]},
    )
    session.add(run)
    session.flush()
    eval_snap = snapshot_evalset(evalset)
    ids: list[str] = []
    for scenario in scenarios:
        for rep in range(req.repeats):
            snap = snapshot_scenario(scenario)
            if req.max_turns:
                snap["max_turns"] = min(snap["max_turns"], req.max_turns)
            title = scenario.name + (f" (run {rep + 1})" if req.repeats > 1 else "")
            conv = Conversation(
                run_id=run.id, source="simulated", status="queued", title=title, mood=scenario.mood,
                prompt_version_id=version.id, scenario_id=scenario.id, eval_set_id=evalset.id,
                prompt_label=label, rendered_prompt=rendered, variables=values, scenario_snapshot=snap,
                evalset_snapshot=eval_snap, gen_config=gen, generated=False,
            )
            session.add(conv)
            session.flush()
            ids.append(conv.id)
    return run, ids


def create_live(session: Session, req: schemas.LiveCreate) -> Conversation:
    version, values, rendered = resolve_prompt(session, req.prompt_version_id, req.variables)
    scenario = get_or_404(session, Scenario, req.scenario_id, "Scenario") if req.scenario_id else None
    mood = req.mood or (scenario.mood if scenario else "")
    conv = Conversation(
        source="live", status="live", title=req.title or (scenario.name if scenario else "Live voice session"),
        mood=mood, prompt_version_id=version.id, scenario_id=scenario.id if scenario else None,
        prompt_label=prompt_label(version), rendered_prompt=rendered, variables=values,
        scenario_snapshot=snapshot_scenario(scenario) if scenario else {}, evalset_snapshot={},
        gen_config=dict(zip(("temperature", "max_tokens"), resolve_generation(session, req.temperature, req.max_tokens))) | {"provider": req.provider, "model": req.model},
        generated=True,
    )
    session.add(conv)
    session.flush()
    return conv


def create_import(session: Session, req: schemas.ImportConversation) -> Conversation:
    evalset = get_or_404(session, EvalSet, req.eval_set_id, "Evaluation set")
    conv = Conversation(
        source="imported", status="queued", title=req.title or "Imported conversation", mood=req.mood,
        eval_set_id=evalset.id, rendered_prompt=req.system_prompt, prompt_label="(imported)",
        evalset_snapshot=snapshot_evalset(evalset), generated=True,
    )
    session.add(conv)
    session.flush()
    for i, t in enumerate(req.turns, start=1):
        session.add(Turn(conversation_id=conv.id, idx=i, role=t.role, content=t.content,
                         latency_ms=t.latency_ms if t.role == "assistant" else None))
    session.flush()
    return conv


# --- export ----------------------------------------------------------------------

def _csv_safe(value) -> str:
    """Neutralise spreadsheet formula injection in exported cells."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in {"=", "+", "-", "@", "\t", "\r"} else text


def run_csv(session: Session, run: TestRun) -> str:
    convs = session.scalars(select(Conversation).where(Conversation.run_id == run.id).order_by(Conversation.created_at)).all()
    keys: list[str] = []
    for c in convs:
        for p in (c.evalset_snapshot or {}).get("params", []):
            if p["key"] not in keys:
                keys.append(p["key"])
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["conversation_id", "title", "mood", "status", "verdict", "score", "reason", "avg_latency_ms", *keys])
    for c in convs:
        by_key = {r.param_key: r for r in c.results}
        writer.writerow([
            _csv_safe(x) for x in (c.id, c.title, c.mood, c.status, c.verdict, c.score, c.verdict_reason, c.avg_latency_ms)
        ] + [_csv_safe(by_key[k].status if k in by_key else "") for k in keys])
    return out.getvalue()
