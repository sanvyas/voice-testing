"""Settings kept in the database: provider credentials (encrypted), per-role models, app options."""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

import llm
from .models import Setting, utcnow
from .secrets import SecretBox
from .service import ServiceError

PROVIDER_IDS = ("groq", "sarvam", "custom")


def get(session: Session, key: str, default=None):
    row = session.get(Setting, key)
    return row.value if row else default


def put(session: Session, key: str, value: dict) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value, row.updated_at = value, utcnow()
    session.flush()


def clean_key(raw: str) -> str:
    key = raw.strip().strip("\"'")
    if not key or len(key) > 500 or re.search(r"\s", key):
        raise ServiceError("That does not look like an API key (it must be a single token without spaces).", 422)
    return key


def clean_base_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    parsed = urlparse(url)
    host = parsed.hostname or ""
    local = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme not in {"https", "http"} or not host or (parsed.scheme == "http" and not local):
        raise ServiceError("The base URL must start with https:// (http:// is only allowed for localhost).", 422)
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise ServiceError("That address is not allowed.", 422)
    except ValueError:
        pass  # a hostname, not an IP literal
    return url


def save_provider(session: Session, box: SecretBox | None, provider: str, *, api_key: str | None, model: str | None, base_url: str | None) -> None:
    if provider not in PROVIDER_IDS:
        raise ServiceError("Unknown provider", 404)
    current = dict(get(session, f"provider.{provider}", {}) or {})
    if api_key:
        if box is None:
            raise ServiceError(
                "Cannot store keys securely: set LAB_SECRET_KEY (32+ characters) in the server environment, "
                "or use a SQLite database so an encryption key file can be created. You can also set the key as an environment variable instead.", 409)
        current["key_enc"] = box.encrypt(clean_key(api_key))
    if model is not None:
        current["model"] = model.strip()[:120]
    if base_url is not None and provider == "custom":
        current["base_url"] = clean_base_url(base_url) if base_url.strip() else ""
    put(session, f"provider.{provider}", current)


def clear_provider_key(session: Session, provider: str) -> None:
    current = dict(get(session, f"provider.{provider}", {}) or {})
    current.pop("key_enc", None)
    put(session, f"provider.{provider}", current)


def load_runtime(session: Session, box: SecretBox | None) -> dict[str, bool]:
    """Push saved settings into the llm module. Returns {provider: stored key unreadable}."""
    runtime = {"keys": {}, "models": {}, "base_urls": {}, "roles": get(session, "roles", {}) or {}}
    unreadable: dict[str, bool] = {}
    for provider in PROVIDER_IDS:
        data = get(session, f"provider.{provider}", {}) or {}
        if data.get("model"):
            runtime["models"][provider] = data["model"]
        if data.get("base_url"):
            runtime["base_urls"][provider] = data["base_url"]
        if data.get("key_enc"):
            key = box.decrypt(data["key_enc"]) if box else None
            if key:
                runtime["keys"][provider] = key
            else:
                unreadable[provider] = True
    llm.set_runtime(runtime)
    return unreadable


def provider_status(session: Session, box: SecretBox | None) -> list[dict]:
    unreadable = load_runtime(session, box)
    cfgs = llm.provider_configs()
    out = []
    for provider in PROVIDER_IDS:
        cfg = cfgs[provider]
        stored = get(session, f"provider.{provider}", {}) or {}
        key = cfg["key"]
        out.append({
            "id": provider, "label": cfg["label"], "configured": bool(key and cfg["url"]),
            "source": cfg["source"], "key_hint": ("…" + key[-4:]) if key and cfg["source"] == "ui" else ("set in server environment" if key else ""),
            "model": cfg["model"], "base_url": cfg["base"] if provider == "custom" else "",
            "stored_key_unreadable": bool(unreadable.get(provider)), "can_store": box is not None,
            "has_stored_key": bool(stored.get("key_enc")),
        })
    return out


def get_roles(session: Session) -> dict:
    stored = get(session, "roles", {}) or {}
    out = {}
    for role in llm.ROLES:
        eff_provider, eff_model = llm.role(role)
        out[role] = {"provider": stored.get(role, {}).get("provider") or "", "model": stored.get(role, {}).get("model") or "",
                     "effective": f"{eff_provider or 'automatic'}{(' · ' + eff_model) if eff_model else ''}"}
    return out


def save_roles(session: Session, roles: dict) -> None:
    clean = {}
    for role in llm.ROLES:
        item = roles.get(role) or {}
        provider = (item.get("provider") or "").strip()
        if provider and provider not in PROVIDER_IDS:
            raise ServiceError(f"Unknown provider for {role}", 422)
        if role == "stt" and provider and provider not in ("groq", "custom"):
            raise ServiceError("Speech recognition supports Groq or an OpenAI-compatible provider.", 422)
        if provider:
            clean[role] = {"provider": provider, "model": (item.get("model") or "").strip()[:120]}
    put(session, "roles", clean)
