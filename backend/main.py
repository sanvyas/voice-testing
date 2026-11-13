import logging
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ai_therapy")

import llm  # noqa: E402  (after load_dotenv so provider settings are visible)
from lab import app as lab_app  # noqa: E402
from prompts import SYSTEM_PROMPT, build_messages  # noqa: E402

app = FastAPI(title="A Space to Talk", version="0.3.0", lifespan=lab_app.lab_lifespan)
lab_app.install(app)  # testing lab: API at /api/lab, UI at /lab

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=400)


async def call_model(messages: list[dict], gen: dict | None = None) -> dict:
    """Try configured providers in order (single attempt each, as before) with the release's model settings."""
    gen = gen or {}
    result = await llm.chat(
        messages, provider=gen.get("provider") or None, model=gen.get("model") or None,
        temperature=gen.get("temperature", 0.7), max_tokens=gen.get("max_tokens", 350), retries=0,
    )
    return {"reply": result.reply, "provider": result.provider, "model": result.model}


def _production_release() -> tuple[str, dict]:
    """The prompt and settings released to production from the lab; the built-in prompt until one is released."""
    from lab import release
    from lab.db import session_scope

    with session_scope() as session:
        dep = release.active(session, "production")
        if dep is not None:
            return release.rendered_for(session, dep), dict(dep.gen or {})
    return SYSTEM_PROMPT, {}


async def production_release() -> tuple[str, dict]:
    import asyncio

    try:
        return await asyncio.to_thread(_production_release)
    except Exception:  # noqa: BLE001 - never take the voice app down because the lab database is unavailable
        logger.exception("Could not load the production release; using the built-in prompt")
        return SYSTEM_PROMPT, {}


@app.get("/", include_in_schema=False)
async def root():
    """The bare address opens the testing lab."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/lab/")


@app.get("/app")
async def home():
    index_file = PROJECT_DIR / "frontend" / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="frontend/index.html not found")
    return FileResponse(index_file, media_type="text/html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness probe: the database must answer."""
    from sqlalchemy import text

    from lab.db import get_engine

    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    history = request.messages  # the whole conversation: the model must remember what was said at the start
    if history[-1].role != "user":
        raise HTTPException(status_code=400, detail="The latest message must be from the user.")

    logger.info("Incoming voice turn; history_messages=%d", len(history))
    system_prompt, gen = await production_release()
    provider_messages = build_messages(system_prompt, [{"role": m.role, "content": m.content} for m in history[:-1]], history[-1].content)

    try:
        result = await call_model(provider_messages, gen)
        logger.info("Voice turn completed; provider=%s model=%s", result["provider"], result["model"])
        return result
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=False)
