"""Chat-completion and speech-to-text client shared by the live app, the mobile API and the testing lab.

Providers speak the OpenAI dialect. A provider is "configured" when it has an API key, taken from
(1) credentials saved through the Settings UI (``set_runtime``), else (2) environment variables.
Everything is resolved at call time so changes take effect without a restart.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("ai_therapy.llm")

PROVIDER_ORDER = ("groq", "sarvam", "custom")
DEFAULT_STT_MODEL = "whisper-large-v3-turbo"
ROLES = ("judge", "simulator", "stt")


class LLMError(RuntimeError):
    """Raised when no provider could produce a result."""


@dataclass
class LLMResult:
    reply: str
    provider: str
    model: str
    latency_ms: int
    usage: dict = field(default_factory=dict)


@dataclass
class Transcript:
    text: str
    provider: str
    model: str
    latency_ms: int


# --- runtime configuration (filled from the database at startup and on every settings change) ---

_runtime: dict = {"keys": {}, "models": {}, "base_urls": {}, "roles": {}}


def set_runtime(data: dict | None) -> None:
    global _runtime
    data = data or {}
    _runtime = {k: dict(data.get(k) or {}) for k in ("keys", "models", "base_urls", "roles")}


def provider_configs() -> dict[str, dict]:
    """Every known provider with its (possibly missing) credentials. UI-saved values win over the environment."""
    rt = _runtime
    custom_base = (rt["base_urls"].get("custom") or os.getenv("OPENAI_COMPAT_BASE_URL") or "").rstrip("/")

    def pick(provider: str, env_key: str, env_model: str, default_model: str) -> dict:
        ui_key, env_val = rt["keys"].get(provider), os.getenv(env_key)
        return {
            "key": ui_key or env_val,
            "source": "ui" if ui_key else ("env" if env_val else None),
            "model": rt["models"].get(provider) or os.getenv(env_model, default_model),
        }

    groq = pick("groq", "GROQ_API_KEY", "GROQ_MODEL", "openai/gpt-oss-20b")
    sarvam = pick("sarvam", "SARVAM_API_KEY", "SARVAM_MODEL", "sarvam-105b")
    custom = pick("custom", "OPENAI_COMPAT_API_KEY", "OPENAI_COMPAT_MODEL", "")
    if not custom_base:
        custom["key"], custom["source"] = None, None
    return {
        "groq": {"label": "Groq", "base": "https://api.groq.com/openai/v1", "url": "https://api.groq.com/openai/v1/chat/completions", **groq},
        "sarvam": {"label": "Sarvam", "base": "https://api.sarvam.ai/v2", "url": "https://api.sarvam.ai/v2/chat/completions", **sarvam},
        "custom": {"label": "OpenAI-compatible", "base": custom_base, "url": f"{custom_base}/chat/completions" if custom_base else "", **custom},
    }


def configured_providers() -> list[str]:
    cfg = provider_configs()
    return [name for name in PROVIDER_ORDER if cfg[name]["key"] and cfg[name]["url"]]


def role(name: str) -> tuple[str | None, str | None]:
    """(provider, model) for a background role: UI setting, else JUDGE_/SIMULATOR_/STT_ env vars."""
    ui = _runtime["roles"].get(name) or {}
    prefix = name.upper()
    provider = ui.get("provider") or os.getenv(f"{prefix}_PROVIDER") or None
    model = ui.get("model") or os.getenv(f"{prefix}_MODEL") or None
    return (provider, model) if provider else (None, None)


# --- HTTP client ----------------------------------------------------------------

_client: httpx.AsyncClient | None = None
_transport: httpx.AsyncBaseTransport | None = None  # injected by tests only


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Test hook: route all provider traffic through a custom transport."""
    global _client, _transport
    _transport = transport
    _client = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0), transport=_transport,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# --- chat -------------------------------------------------------------------------

_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def _extra_params(provider: str, model: str) -> dict:
    """Provider-specific knobs. Groq's gpt-oss models spend max_tokens on hidden reasoning, which can leave the
    spoken reply empty; low reasoning effort keeps latency down and the answer inside the budget."""
    if provider == "groq" and "gpt-oss" in model:
        effort = os.getenv("GROQ_REASONING_EFFORT", "low").strip().lower()
        if effort in {"low", "medium", "high"}:
            return {"reasoning_effort": effort}
    return {}


async def _post_chat(cfg: dict, payload: dict) -> httpx.Response:
    return await _get_client().post(
        cfg["url"], headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"}, json=payload
    )


async def _call_once(name: str, cfg: dict, model: str, messages: list[dict], temperature: float, max_tokens: int) -> LLMResult:
    started = time.perf_counter()
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    extra = _extra_params(name, model)
    response = await _post_chat(cfg, {**payload, **extra})
    if response.status_code == 400 and extra and "reasoning" in response.text.lower():
        logger.warning("provider=%s rejected reasoning parameters; retrying without them", cfg["label"])
        response = await _post_chat(cfg, payload)
    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info("provider=%s model=%s http=%s latency_ms=%d", cfg["label"], model, response.status_code, latency_ms)
    response.raise_for_status()
    data = response.json()
    choice = data["choices"][0]
    reply = (choice.get("message") or {}).get("content")
    if not isinstance(reply, str) or not reply.strip():
        if choice.get("finish_reason") == "length":
            raise ValueError("The model used all of max_tokens before answering (reasoning models need more headroom): raise max tokens")
        raise ValueError("Provider returned an empty response")
    return LLMResult(reply=reply.strip(), provider=cfg["label"], model=data.get("model", model), latency_ms=latency_ms, usage=data.get("usage") or {})


def _retry_delay(exc: Exception, attempt: int) -> float | None:
    """Seconds to wait before retrying, or None if the error is not retryable."""
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code not in _RETRYABLE_STATUS:
            return None
        retry_after = exc.response.headers.get("retry-after", "")
        if retry_after.isdigit():
            return min(float(retry_after), 15.0)
    elif not isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return None
    return min(0.6 * (2**attempt), 8.0)


def _describe(exc: Exception) -> str:
    """Short, user-facing explanation of a provider failure."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        try:
            detail = exc.response.json().get("error", {})
            detail = detail.get("message") if isinstance(detail, dict) else str(detail)
        except Exception:  # noqa: BLE001
            detail = exc.response.text[:200]
        hint = {401: "the API key was rejected", 403: "access denied for this key or model", 404: "model or endpoint not found", 429: "rate limit or quota reached"}.get(code, "")
        return f"HTTP {code}{' (' + hint + ')' if hint else ''}: {str(detail or '')[:240]}".strip()
    return str(exc)[:300] or exc.__class__.__name__


async def chat(
    messages: list[dict], *, provider: str | None = None, model: str | None = None,
    temperature: float = 0.7, max_tokens: int = 350, retries: int = 2,
) -> LLMResult:
    """Send ``messages`` to a provider and return the reply.

    With ``provider=None`` configured providers are tried in order (Groq, Sarvam, custom), as in production.
    A ``model`` override requires an explicit provider. Transient failures (429/5xx/timeouts) are retried.
    """
    cfgs = provider_configs()
    if provider is not None:
        if provider not in cfgs:
            raise LLMError(f"Unknown provider '{provider}'.")
        chain = [provider]
    else:
        if model:
            raise LLMError("A model override requires an explicit provider.")
        chain = configured_providers()
    if not chain:
        raise LLMError("No LLM provider is connected. Add your Groq API key in Settings.")

    errors: list[str] = []
    for name in chain:
        cfg = cfgs[name]
        if not cfg["key"] or not cfg["url"]:
            errors.append(f"{cfg['label']}: not configured")
            continue
        use_model = model or cfg["model"]
        if not use_model:
            errors.append(f"{cfg['label']}: no model set")
            continue
        for attempt in range(retries + 1):
            try:
                return await _call_once(name, cfg, use_model, messages, temperature, max_tokens)
            except Exception as exc:  # noqa: BLE001 - provider failures are reported, not fatal
                delay = _retry_delay(exc, attempt)
                if delay is not None and attempt < retries:
                    logger.warning("provider=%s transient failure (%s); retrying in %.1fs", cfg["label"], exc, delay)
                    await asyncio.sleep(delay)
                    continue
                logger.warning("provider=%s failed: %s", cfg["label"], exc)
                errors.append(f"{cfg['label']}: {_describe(exc)}")
                break
    raise LLMError("All configured providers failed. " + " | ".join(errors))


# --- speech to text ---------------------------------------------------------------

async def transcribe(
    audio: bytes, filename: str, content_type: str, *, language: str | None = None,
    provider: str | None = None, model: str | None = None, retries: int = 1,
) -> Transcript:
    """Transcribe a recorded clip (webm/ogg/mp4/m4a/wav/mp3) with an OpenAI-compatible Whisper endpoint (Groq by default)."""
    cfgs = provider_configs()
    role_provider, role_model = role("stt")
    name = provider or role_provider or next((p for p in ("groq", "custom") if p in configured_providers()), None)
    if not name or name not in ("groq", "custom") or not (cfgs[name]["key"] and cfgs[name]["base"]):
        raise LLMError("Speech recognition needs a connected Groq (or OpenAI-compatible) provider. Add your Groq API key in Settings.")
    cfg = cfgs[name]
    use_model = model or role_model or DEFAULT_STT_MODEL
    data = {"model": use_model, "response_format": "json", "temperature": "0"}
    if language:
        data["language"] = language.split("-")[0].lower()  # Whisper wants ISO-639-1: en-IN -> en
    last = "unknown error"
    for attempt in range(retries + 1):
        started = time.perf_counter()
        try:
            response = await _get_client().post(
                f"{cfg['base']}/audio/transcriptions", headers={"Authorization": f"Bearer {cfg['key']}"},
                data=data, files={"file": (filename or "audio.webm", audio, content_type or "application/octet-stream")},
            )
            response.raise_for_status()
            text = str(response.json().get("text", "")).strip()
            return Transcript(text, cfg["label"], use_model, int((time.perf_counter() - started) * 1000))
        except Exception as exc:  # noqa: BLE001
            delay = _retry_delay(exc, attempt)
            last = _describe(exc)
            if delay is not None and attempt < retries:
                await asyncio.sleep(delay)
                continue
            break
    raise LLMError(f"Speech recognition failed. {cfg['label']}: {last}")


# --- connection test and model discovery -----------------------------------------

NON_CHAT_HINTS = ("whisper", "tts", "orpheus", "playai", "guard", "embed", "moderation")


async def list_models(provider: str) -> dict:
    """Models the provider's key can use, split into chat and speech-to-text. Sarvam has no listing endpoint."""
    cfg = provider_configs().get(provider)
    if not cfg or not cfg["key"] or provider == "sarvam" or not cfg["base"]:
        return {"chat": [], "stt": []}
    response = await _get_client().get(f"{cfg['base']}/models", headers={"Authorization": f"Bearer {cfg['key']}"})
    response.raise_for_status()
    ids = sorted({m.get("id", "") for m in response.json().get("data", []) if m.get("id")})
    return {
        "chat": [i for i in ids if not any(h in i.lower() for h in NON_CHAT_HINTS)],
        "stt": [i for i in ids if "whisper" in i.lower()],
    }


async def test_provider(provider: str) -> dict:
    """Make one tiny real request. Returns {ok, message, latency_ms, models}."""
    cfg = provider_configs().get(provider)
    if not cfg or not cfg["key"] or not cfg["url"]:
        return {"ok": False, "message": "No API key saved for this provider.", "latency_ms": None, "models": {"chat": [], "stt": []}}
    models = {"chat": [], "stt": []}
    try:
        models = await list_models(provider)
    except Exception as exc:  # noqa: BLE001 - listing is a convenience; the chat ping below is the real test
        logger.info("model listing failed for %s: %s", provider, exc)
    try:
        result = await chat([{"role": "user", "content": "Reply with the single word: ok"}], provider=provider, temperature=0, max_tokens=64, retries=0)
        return {"ok": True, "message": f"Connected. {result.model} answered in {result.latency_ms} ms.", "latency_ms": result.latency_ms, "models": models}
    except LLMError as exc:
        return {"ok": False, "message": str(exc).replace("All configured providers failed. ", ""), "latency_ms": None, "models": models}
