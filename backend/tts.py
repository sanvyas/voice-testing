"""Text-to-speech for the lab: Google Cloud TTS (Standard / WaveNet) and Chatterbox on DeepInfra.

Same conventions as ``llm.py``: keys come from the Settings UI (``set_runtime``) or environment variables, are resolved
at call time, and share llm's HTTP client (so tests can inject a transport with ``llm.set_transport``).
"Device" is not an engine here: it means the browser speaks and the server is not involved.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import llm

ENGINES = {
    # price is per 1M characters, as read from each vendor's pricing page on 2026-11-07
    "google": {"label": "Google Cloud (Standard / WaveNet)", "key_env": "GOOGLE_TTS_API_KEY", "price_per_m": 4.0, "free_chars": 4_000_000,
               "cap_env": "TTS_CAP_CHARS_GOOGLE", "default_cap": 3_900_000, "key_help": "Google Cloud console → APIs → Cloud Text-to-Speech API → enable, then Credentials → API key"},
    "chatterbox": {"label": "Chatterbox (DeepInfra)", "key_env": "DEEPINFRA_API_KEY", "price_per_m": 1.0, "free_chars": 0,
                   "cap_env": "TTS_CAP_CHARS_CHATTERBOX", "default_cap": 1_000_000, "key_help": "deepinfra.com → Dashboard → API keys"},
}
KEY_NAMES = {"google": "google", "chatterbox": "deepinfra"}  # engine -> stored key name
MAX_CHARS = 4500  # Google accepts 5000 bytes, DeepInfra 5000 characters

GOOGLE_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
DEEPINFRA_URL = "https://api.deepinfra.com/v1/inference/ResembleAI/chatterbox-multilingual"
CHATTERBOX_LANGS = {  # language_id -> name (Chatterbox Multilingual, 23 languages)
    "ar": "Arabic", "da": "Danish", "de": "German", "el": "Greek", "en": "English", "es": "Spanish", "fi": "Finnish", "fr": "French",
    "he": "Hebrew", "hi": "Hindi", "it": "Italian", "ja": "Japanese", "ko": "Korean", "ms": "Malay", "nl": "Dutch", "no": "Norwegian",
    "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "sv": "Swedish", "sw": "Swahili", "tr": "Turkish", "zh": "Chinese"}

_VOICES: dict = json.loads((Path(__file__).parent / "google_voices.json").read_text(encoding="utf-8"))  # locale -> tier -> ["AF", "BM", ...]


class TTSError(RuntimeError):
    """A readable reason the speech could not be produced."""


@dataclass
class Speech:
    audio: bytes
    mime: str
    engine: str
    voice: str
    chars: int
    latency_ms: int
    cost_usd: float | None = None  # what the vendor reported, when it reports one


_runtime: dict = {"keys": {}, "active": "device", "google_tier": "Wavenet", "google_gender": "F"}


def set_runtime(data: dict | None) -> None:
    global _runtime
    base = {"keys": {}, "active": "device", "google_tier": "Wavenet", "google_gender": "F"}
    base.update(data or {})
    base["keys"] = dict(base.get("keys") or {})
    _runtime = base


def active() -> str:
    return _runtime["active"] if _runtime["active"] in ("device", *ENGINES) else "device"


def key_for(engine: str) -> tuple[str | None, str | None]:
    """(key, source) where source is 'ui', 'env' or None."""
    ui = _runtime["keys"].get(KEY_NAMES[engine])
    if ui:
        return ui, "ui"
    env = os.getenv(ENGINES[engine]["key_env"])
    return (env, "env") if env else (None, None)


def cap_chars(engine: str) -> int:
    raw = os.getenv(ENGINES[engine]["cap_env"], "")
    return int(raw) if raw.isdigit() else ENGINES[engine]["default_cap"]


def google_voice(language: str, tier: str | None = None, gender: str | None = None) -> str:
    """Pick a voice name like hi-IN-Wavenet-A. Falls back to Standard when a language has no WaveNet voice."""
    locale = _locale(language)
    tiers = _VOICES.get(locale)
    if not tiers:
        raise TTSError(f"Google has no Standard or WaveNet voice for {language}.")
    tier = tier or _runtime["google_tier"]
    gender = (gender or _runtime["google_gender"])[:1].upper()
    use = tier if tier in tiers else next(iter(tiers))
    options = tiers[use]
    pick = next((v for v in options if v[1] == gender), options[0])
    return f"{locale}-{use}-{pick[0]}"


def _locale(language: str) -> str:
    language = (language or "en-US").replace("_", "-")
    if language in _VOICES:
        return language
    base = language.split("-")[0].lower()
    return next((loc for loc in ("%s-IN" % base, "%s-US" % base, "%s-%s" % (base, base.upper())) if loc in _VOICES), language)


def chatterbox_language(language: str) -> str:
    code = (language or "en").split("-")[0].lower()
    if code == "nb":
        code = "no"
    if code not in CHATTERBOX_LANGS:
        raise TTSError(f"Chatterbox cannot speak {language}. It supports: {', '.join(sorted(CHATTERBOX_LANGS.values()))}.")
    return code


def engine_status() -> list[dict]:
    out = []
    for engine, meta in ENGINES.items():
        key, source = key_for(engine)
        out.append({"id": engine, "label": meta["label"], "configured": bool(key), "source": source,
                    "key_hint": ("…" + key[-4:]) if key and source == "ui" else ("set in server environment" if key else ""),
                    "price_per_m": meta["price_per_m"], "free_chars": meta["free_chars"], "cap_chars": cap_chars(engine), "key_help": meta["key_help"]})
    return out


def clean_text(text: str) -> str:
    text = re.sub(r"[*_`#>]+", "", text or "")  # markdown marks would be read out loud
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        text = cut[: max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "), cut.rfind("। "))  + 1] or cut
    return text


def _explain(exc: Exception, label: str) -> str:
    detail = llm._describe(exc) if hasattr(llm, "_describe") else str(exc)
    return f"{label}: {detail}"


async def synthesize(engine: str, text: str, language: str) -> Speech:
    if engine not in ENGINES:
        raise TTSError("This voice is played by your device, not the server.")
    key, _ = key_for(engine)
    if not key:
        raise TTSError(f"{ENGINES[engine]['label']} has no API key yet. Add it in Settings.")
    text = clean_text(text)
    if not text:
        raise TTSError("Nothing to say.")
    started = time.perf_counter()
    try:
        if engine == "google":
            voice, audio, mime, cost = await _google(key, text, language)
        else:
            voice, audio, mime, cost = await _chatterbox(key, text, language)
    except TTSError:
        raise
    except Exception as exc:  # noqa: BLE001 - network, auth and quota problems all become one readable message
        raise TTSError(_explain(exc, ENGINES[engine]["label"])) from None
    return Speech(audio, mime, engine, voice, len(text), int((time.perf_counter() - started) * 1000), cost)


async def _google(key: str, text: str, language: str):
    voice = google_voice(language)
    body = {"input": {"text": text}, "voice": {"languageCode": voice[:5], "name": voice}, "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0}}
    response = await llm.http_client().post(GOOGLE_URL, headers={"X-Goog-Api-Key": key}, json=body)
    response.raise_for_status()
    audio = base64.b64decode(response.json().get("audioContent") or "")
    if not audio:
        raise TTSError("Google returned no audio.")
    return voice, audio, "audio/mpeg", None


async def _chatterbox(key: str, text: str, language: str):
    code = chatterbox_language(language)
    body = {"text": text, "language_id": code, "response_format": "mp3", "exaggeration": 0.5, "cfg": 0.5}
    response = await llm.http_client().post(DEEPINFRA_URL, headers={"Authorization": f"Bearer {key}"}, json=body)
    response.raise_for_status()
    if response.headers.get("content-type", "").startswith("audio/"):
        return f"chatterbox-{code}", response.content, response.headers["content-type"].split(";")[0], None
    data = response.json()
    audio_field = data.get("audio") or ""
    if audio_field.startswith(("http://", "https://")):
        raise TTSError("DeepInfra returned a link instead of audio data.")
    audio = base64.b64decode(audio_field.split(",", 1)[-1]) if audio_field else b""
    if not audio:
        raise TTSError("DeepInfra returned no audio.")
    cost = (data.get("inference_status") or {}).get("cost")
    return f"chatterbox-{code}", audio, "audio/mpeg", float(cost) if isinstance(cost, (int, float)) else None
