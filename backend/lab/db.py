"""Engine/session management and migrations."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import BACKEND_DIR, Settings

logger = logging.getLogger("ai_therapy.lab.db")

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def make_engine(url: str, schema: str | None = None) -> Engine:
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if ":memory:" in url or url in {"sqlite://", "sqlite:///"}:
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
        else:
            path = url.split("sqlite:///", 1)[-1]
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    else:
        # Postgres behind a shared pooler (e.g. Supabase): stay small so we never starve the other app on the same database
        kwargs.update(pool_size=3, max_overflow=2, pool_recycle=300)
    engine = create_engine(url, **kwargs)
    if schema and not url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _schema(dbapi_conn, _record):  # every connection works only inside our own schema
            cur = dbapi_conn.cursor()
            cur.execute(f'SET search_path TO "{schema}"')
            cur.close()
            dbapi_conn.commit()

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

    return engine


def _alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def init_db(settings: Settings) -> None:
    """Create the engine and bring the schema to the latest migration."""
    global _engine, _SessionLocal
    _engine = make_engine(settings.database_url, settings.database_schema)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)
    cfg = _alembic_config(settings.database_url)
    cfg.attributes["connection"] = _engine
    command.upgrade(cfg, "head")
    logger.info("Database ready (%s)", _engine.dialect.name)


def dispose_db() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database is not initialised")
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on error."""
    if _SessionLocal is None:
        raise RuntimeError("Database is not initialised")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session
