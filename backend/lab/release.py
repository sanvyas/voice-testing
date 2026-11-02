"""Releases (staging / production), app API keys, and the evidence shown before promoting."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import service
from .models import ApiKey, Deployment, TestRun, utcnow
from .service import ServiceError, get_or_404

ENVIRONMENTS = ("staging", "production")
MIN_PASS_RATE_TO_SHIP = 80.0  # below this, promoting to production needs explicit confirmation


def check_env(env: str) -> str:
    if env not in ENVIRONMENTS:
        raise ServiceError("Environment must be 'staging' or 'production'", 422)
    return env


def active(session: Session, env: str) -> Deployment | None:
    return session.scalars(
        select(Deployment).where(Deployment.environment == env, Deployment.active.is_(True)).order_by(Deployment.created_at.desc()).limit(1)
    ).first()


def evidence(session: Session, version_id: str, values: dict) -> dict:
    """What the lab has measured for exactly this prompt version AND these variable values.
    A run with different variables tested a different prompt, so it is not evidence."""
    candidates = session.scalars(
        select(TestRun).where(TestRun.prompt_version_id == version_id, TestRun.status == "completed").order_by(TestRun.created_at.desc()).limit(60)
    ).all()
    runs = [r for r in candidates if (r.config or {}).get("variables") == values][:3]
    counts = service.run_counts(session, [r.id for r in runs])
    items = [service.run_out(r, counts[r.id]) for r in runs]
    latest = next((i for i in items if i["pass_rate"] is not None), None)
    return {
        "runs": [{"id": i["id"], "name": i["name"], "pass_rate": i["pass_rate"], "passed": i["counts"]["passed"], "total": i["counts"]["total"], "created_at": i["created_at"]} for i in items],
        "latest_pass_rate": latest["pass_rate"] if latest else None,
        "tested": latest is not None,
    }


def deployment_out(d: Deployment) -> dict:
    v = d.prompt_version
    return {
        "id": d.id, "environment": d.environment, "active": d.active, "note": d.note, "gen": d.gen, "variables": d.variables,
        "prompt_version_id": v.id, "prompt_id": v.prompt_id, "prompt_label": service.prompt_label(v), "version": v.version,
        "evidence": d.evidence, "created_at": service.iso(d.created_at),
    }


def promote(session: Session, env: str, version_id: str, variables: dict, gen: dict, note: str, confirm: bool) -> Deployment:
    check_env(env)
    version, values, _rendered = service.resolve_prompt(session, version_id, variables)  # validates variables
    ev = evidence(session, version_id, values)
    if env == "production" and not confirm:
        if not ev["tested"]:
            raise ServiceError("This prompt version has no completed test run. Run a test first, or confirm to ship it untested.", 409)
        if ev["latest_pass_rate"] < MIN_PASS_RATE_TO_SHIP:
            raise ServiceError(f"Its latest test run passed only {ev['latest_pass_rate']:g}% (below {MIN_PASS_RATE_TO_SHIP:g}%). Confirm to ship anyway.", 409)
    for old in session.scalars(select(Deployment).where(Deployment.environment == env, Deployment.active.is_(True))):
        old.active = False
    dep = Deployment(environment=env, prompt_version_id=version.id, variables=values, gen=gen, note=note, evidence=ev, active=True)
    session.add(dep)
    session.flush()
    return dep


def rendered_for(session: Session, dep: Deployment) -> str:
    return service.resolve_prompt(session, dep.prompt_version_id, dep.variables)[2]


# --- API keys ------------------------------------------------------------------

def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_api_key(session: Session, name: str, env: str) -> tuple[ApiKey, str]:
    check_env(env)
    raw = "vtl_" + secrets.token_urlsafe(32)
    row = ApiKey(name=name, environment=env, prefix=raw[:8], key_hash=hash_key(raw))
    session.add(row)
    session.flush()
    return row, raw


def api_key_out(k: ApiKey) -> dict:
    return {"id": k.id, "name": k.name, "environment": k.environment, "prefix": k.prefix, "created_at": service.iso(k.created_at),
            "last_used_at": service.iso(k.last_used_at), "revoked": k.revoked_at is not None}


def lookup_key(session: Session, raw: str) -> ApiKey | None:
    row = session.scalars(select(ApiKey).where(ApiKey.key_hash == hash_key(raw))).first()
    if row is None or row.revoked_at is not None:
        return None
    if row.last_used_at is None or utcnow() - _aware(row.last_used_at) > timedelta(seconds=60):
        row.last_used_at = utcnow()
    return row


def _aware(dt):
    from datetime import timezone
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
