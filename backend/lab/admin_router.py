"""Admin endpoints for connecting providers, managing app keys and releases (all behind the lab token)."""
from __future__ import annotations

import llm
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import release, service, settings_store
from .db import get_session
from .models import ApiKey, Deployment, EvalSet, utcnow
from .runner import run_db
from .schemas import Strict
from .security import require_auth
from .service import ServiceError, get_or_404

router = APIRouter(dependencies=[Depends(require_auth)])
MAX_AUDIO_BYTES = 12 * 1024 * 1024


def _box(request: Request):
    return request.app.state.lab_secret_box


class ProviderUpdate(Strict):
    api_key: str | None = Field(default=None, max_length=600)
    model: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=300)


class RolesUpdate(Strict):
    judge: dict = Field(default_factory=dict)
    simulator: dict = Field(default_factory=dict)
    stt: dict = Field(default_factory=dict)


class AppSettingsUpdate(Strict):
    eval_set_id: str | None = None


class GenerationUpdate(Strict):
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(ge=50, le=2000)


class ApiKeyCreate(Strict):
    name: str = Field(min_length=1, max_length=120)
    environment: str


class DeployRequest(Strict):
    environment: str
    prompt_version_id: str
    variables: dict[str, str] = Field(default_factory=dict)
    temperature: float | None = Field(default=None, ge=0, le=2)   # None = the saved setting
    max_tokens: int | None = Field(default=None, ge=50, le=2000)
    provider: str | None = None
    model: str | None = Field(default=None, max_length=120)
    note: str = Field(default="", max_length=500)
    confirm: bool = False


# --- providers -------------------------------------------------------------------

@router.get("/settings/providers")
def list_providers(request: Request, session: Session = Depends(get_session)):
    return settings_store.provider_status(session, _box(request))


@router.put("/settings/providers/{provider}")
async def update_provider(provider: str, body: ProviderUpdate, request: Request):
    box = _box(request)

    def work(session: Session):
        settings_store.save_provider(session, box, provider, api_key=body.api_key, model=body.model, base_url=body.base_url)
        return settings_store.provider_status(session, box)

    statuses = await run_db(work)
    status = next(s for s in statuses if s["id"] == provider)
    warning = "Groq keys normally start with gsk_. Double-check what you pasted." if provider == "groq" and body.api_key and not body.api_key.strip().strip("\"'").startswith("gsk_") else ""
    return {"provider": status, "warning": warning}


@router.delete("/settings/providers/{provider}/key", status_code=204)
async def remove_provider_key(provider: str, request: Request):
    def work(session: Session):
        settings_store.clear_provider_key(session, provider)
        settings_store.load_runtime(session, _box(request))
    await run_db(work)
    return Response(status_code=204)


@router.post("/settings/providers/{provider}/test")
async def test_provider(provider: str):
    if provider not in settings_store.PROVIDER_IDS:
        raise ServiceError("Unknown provider", 404)
    return await llm.test_provider(provider)


@router.get("/settings/roles")
def get_roles(session: Session = Depends(get_session)):
    return settings_store.get_roles(session)


@router.put("/settings/roles")
async def put_roles(body: RolesUpdate, request: Request):
    def work(session: Session):
        settings_store.save_roles(session, body.model_dump())
        settings_store.load_runtime(session, _box(request))
        return settings_store.get_roles(session)
    return await run_db(work)


@router.get("/settings/app")
def get_app_settings(session: Session = Depends(get_session)):
    return {"eval_set_id": (settings_store.get(session, "app", {}) or {}).get("eval_set_id")}


@router.put("/settings/app")
def put_app_settings(body: AppSettingsUpdate, session: Session = Depends(get_session)):
    if body.eval_set_id:
        get_or_404(session, EvalSet, body.eval_set_id, "Evaluation set")
    settings_store.put(session, "app", {"eval_set_id": body.eval_set_id})
    return {"eval_set_id": body.eval_set_id}


# --- how the assistant talks ----------------------------------------------------

@router.get("/settings/generation")
def get_generation(session: Session = Depends(get_session)):
    return service.generation_settings(session)


@router.put("/settings/generation")
def put_generation(body: GenerationUpdate, session: Session = Depends(get_session)):
    return service.save_generation(session, body.temperature, body.max_tokens)


# --- app API keys ----------------------------------------------------------------

@router.get("/api-keys")
def list_api_keys(session: Session = Depends(get_session)):
    return [release.api_key_out(k) for k in session.scalars(select(ApiKey).order_by(ApiKey.created_at.desc()))]


@router.post("/api-keys", status_code=201)
def create_api_key(body: ApiKeyCreate, session: Session = Depends(get_session)):
    row, raw = release.create_api_key(session, body.name, body.environment)
    return {**release.api_key_out(row), "key": raw, "note": "Copy this key now. It is stored hashed and cannot be shown again."}


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: str, session: Session = Depends(get_session)):
    get_or_404(session, ApiKey, key_id, "API key").revoked_at = utcnow()
    return Response(status_code=204)


# --- releases --------------------------------------------------------------------

@router.get("/deployments")
def list_deployments(environment: str | None = None, session: Session = Depends(get_session)):
    q = select(Deployment).order_by(Deployment.created_at.desc()).limit(60)
    if environment:
        q = q.where(Deployment.environment == release.check_env(environment))
    return [release.deployment_out(d) for d in session.scalars(q)]


@router.get("/deployments/active")
def active_deployments(session: Session = Depends(get_session)):
    out = {}
    for env in release.ENVIRONMENTS:
        dep = release.active(session, env)
        out[env] = release.deployment_out(dep) if dep else None
    return out


@router.post("/deployments", status_code=201)
def deploy(body: DeployRequest, session: Session = Depends(get_session)):
    if body.provider and body.provider not in settings_store.PROVIDER_IDS:
        raise ServiceError("Unknown provider", 422)
    if body.model and not body.provider:
        raise ServiceError("Choose a provider to use a specific model", 422)
    temperature, max_tokens = service.resolve_generation(session, body.temperature, body.max_tokens)
    gen = {"temperature": temperature, "max_tokens": max_tokens, "provider": body.provider, "model": body.model}
    dep = release.promote(session, body.environment, body.prompt_version_id, body.variables, gen, body.note, body.confirm)
    return release.deployment_out(dep)


class EvidenceRequest(Strict):
    prompt_version_id: str
    variables: dict[str, str] = Field(default_factory=dict)


@router.post("/deployments/evidence")
def version_evidence(body: EvidenceRequest, session: Session = Depends(get_session)):
    """Test results that apply to exactly this prompt version with these variable values."""
    _version, values, _rendered = service.resolve_prompt(session, body.prompt_version_id, body.variables)
    return {**release.evidence(session, body.prompt_version_id, values), "min_pass_rate": release.MIN_PASS_RATE_TO_SHIP}


# --- speech to text for the lab's live page ---------------------------------------

@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = Form("")):
    audio = await file.read(MAX_AUDIO_BYTES + 1)
    if not audio:
        raise ServiceError("Empty recording", 422)
    if len(audio) > MAX_AUDIO_BYTES:
        raise ServiceError("Recording is too long (limit about 12 MB).", 413)
    try:
        result = await llm.transcribe(audio, file.filename or "audio.webm", file.content_type or "", language=language or None)
    except llm.LLMError as exc:
        raise ServiceError(str(exc), 502) from None
    return {"text": result.text, "latency_ms": result.latency_ms, "model": result.model}
