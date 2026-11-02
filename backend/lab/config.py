"""Lab settings, read from the environment (backend/.env is loaded by main.py)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    database_schema: str | None
    api_tokens: tuple[str, ...]
    open_access: bool
    max_concurrency: int
    max_conversations_per_run: int
    judge_provider: str | None
    judge_model: str | None
    simulator_provider: str | None
    simulator_model: str | None
    seed_defaults: bool
    secret_key: str | None
    app_rate_limit_per_min: int
    cors_origins: tuple[str, ...]

    @property
    def is_production(self) -> bool:
        return self.env == "production"


def normalize_database_url(url: str) -> str:
    """Render/Heroku hand out postgres:// or postgresql://; SQLAlchemy needs the driver named explicitly."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def load_settings() -> Settings:
    env = os.getenv("APP_ENV", "development").strip().lower()
    default_db = f"sqlite:///{BACKEND_DIR / 'data' / 'lab.db'}"
    tokens = tuple(t.strip() for t in os.getenv("LAB_API_TOKENS", "").split(",") if t.strip())
    return Settings(
        env=env,
        database_url=normalize_database_url(os.getenv("DATABASE_URL") or default_db),
        database_schema=os.getenv("DATABASE_SCHEMA") or None,
        api_tokens=tokens,
        open_access=os.getenv("LAB_OPEN_ACCESS", "").strip().lower() in {"1", "true", "yes"},
        max_concurrency=max(1, _int("LAB_MAX_CONCURRENCY", 4)),
        max_conversations_per_run=max(1, _int("LAB_MAX_CONVERSATIONS_PER_RUN", 60)),
        judge_provider=os.getenv("JUDGE_PROVIDER") or None,
        judge_model=os.getenv("JUDGE_MODEL") or None,
        simulator_provider=os.getenv("SIMULATOR_PROVIDER") or None,
        simulator_model=os.getenv("SIMULATOR_MODEL") or None,
        seed_defaults=os.getenv("LAB_SEED_DEFAULTS", "true").strip().lower() not in {"0", "false", "no"},
        secret_key=os.getenv("LAB_SECRET_KEY") or None,
        app_rate_limit_per_min=max(1, _int("APP_RATE_LIMIT_PER_MIN", 60)),
        cors_origins=tuple(o.strip().rstrip("/") for o in os.getenv("APP_CORS_ORIGINS", "").split(",") if o.strip()),
    )


def validate_for_startup(settings: Settings) -> None:
    """Fail fast on unsafe production configuration."""
    if settings.is_production and not settings.api_tokens and not settings.open_access:
        raise RuntimeError(
            "APP_ENV=production requires LAB_API_TOKENS (comma-separated secrets) to protect the testing lab, "
            "or LAB_OPEN_ACCESS=true to run it without sign-in on purpose."
        )
    if settings.database_schema and not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", settings.database_schema):
        raise RuntimeError("DATABASE_SCHEMA must be a simple lowercase identifier such as voice_lab.")
    if settings.secret_key and len(settings.secret_key) < 32:
        raise RuntimeError("LAB_SECRET_KEY must be at least 32 characters.")
    for token in settings.api_tokens:
        if settings.is_production and len(token) < 24:
            raise RuntimeError("Each LAB_API_TOKENS entry must be at least 24 characters in production.")
