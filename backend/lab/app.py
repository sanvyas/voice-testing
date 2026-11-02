"""Wiring: lifespan, router, error handling, security headers and the static UI."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import llm
from . import db, settings_store
from .secrets import load_box
from .config import load_settings, validate_for_startup
from .runner import Runner
from .seed import seed_defaults
from .service import ServiceError

logger = logging.getLogger("ai_therapy.lab")


async def self_check() -> None:
    """Log whether each connected provider really answers, so a bad key shows up in the logs at deploy time."""
    for name in llm.configured_providers():
        try:
            result = await llm.test_provider(name)
            (logger.info if result["ok"] else logger.error)("Self-check %s: %s", name, result["message"])
        except Exception:  # noqa: BLE001
            logger.exception("Self-check %s crashed", name)
    if not llm.configured_providers():
        logger.warning("Self-check: no LLM provider is connected yet")
        return
    # Memory probe: a name given at the start of a long conversation must still be known 30 exchanges later.
    try:
        from prompts import build_messages

        history = [{"role": "user", "content": "Hi, my name is Priya and I live in Pune."}, {"role": "assistant", "content": "Nice to meet you, Priya. How are you feeling today?"}]
        for i in range(30):
            history += [{"role": "user", "content": f"Update {i}: work was busy and I had chai."}, {"role": "assistant", "content": "That sounds like a full day. What stood out?"}]
        result = await llm.chat(build_messages("You are a warm voice companion. Reply in one short sentence.", history, "Sorry, what is my name again?"), max_tokens=300, retries=1)
        remembered = "priya" in result.reply.lower()
        (logger.info if remembered else logger.error)("Self-check memory: %s (%s answered: %r)", "OK, remembers the opening of a 60-message conversation" if remembered else "FAILED", result.model, result.reply[:80])
    except Exception as exc:  # noqa: BLE001
        logger.error("Self-check memory: could not run: %s", exc)

UI_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "lab"

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


@asynccontextmanager
async def lab_lifespan(app: FastAPI):
    settings = load_settings()
    validate_for_startup(settings)
    db.init_db(settings)
    if settings.seed_defaults:
        with db.session_scope() as session:
            seed_defaults(session)
    app.state.lab_settings = settings
    app.state.lab_secret_box = load_box(settings.secret_key, settings.database_url)
    with db.session_scope() as session:  # provider keys / role models saved through the Settings page
        unreadable = settings_store.load_runtime(session, app.state.lab_secret_box)
    if unreadable:
        logger.warning("Stored credentials for %s cannot be decrypted (encryption key changed). Re-enter them in Settings.", ", ".join(unreadable))
    app.state.lab_runner = Runner(settings)
    await app.state.lab_runner.recover()
    check = asyncio.create_task(self_check())
    logger.info("Testing lab ready (env=%s, auth=%s)", settings.env, "on" if settings.api_tokens and not settings.open_access else "OFF")
    try:
        yield
    finally:
        check.cancel()
        await app.state.lab_runner.shutdown()
        await llm.close_client()
        db.dispose_db()


def install(app: FastAPI) -> None:
    from .router import router

    @app.exception_handler(ServiceError)
    async def _service_error(_request: Request, exc: ServiceError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.middleware("http")
    async def _headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if path.startswith("/api/lab"):
            response.headers["Cache-Control"] = "no-store"
        if path.startswith("/lab"):
            response.headers["Content-Security-Policy"] = CSP
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Cache-Control"] = "no-cache"
        return response

    from .admin_router import router as admin_router
    from .api_v1 import router as v1_router

    @app.middleware("http")
    async def _cors_v1(request: Request, call_next):
        """CORS for browser clients of the app API on other origins (native apps do not need it)."""
        if not request.url.path.startswith("/api/v1"):
            return await call_next(request)
        origin = request.headers.get("origin", "")
        allowed = origin and origin.rstrip("/") in request.app.state.lab_settings.cors_origins
        if request.method == "OPTIONS" and request.headers.get("access-control-request-method"):
            response = JSONResponse({}, status_code=204 if allowed else 403)
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-API-Key"
            response.headers["Access-Control-Max-Age"] = "600"
        else:
            response = await call_next(request)
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router, prefix="/api/lab", tags=["lab"])
    app.include_router(admin_router, prefix="/api/lab", tags=["lab"])
    app.include_router(v1_router, prefix="/api/v1")

    if UI_DIR.exists():
        app.mount("/lab", StaticFiles(directory=UI_DIR, html=True), name="lab-ui")
