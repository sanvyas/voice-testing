"""Alembic environment. Uses the app's engine when run programmatically (init_db),
or DATABASE_URL / the default SQLite path when run from the CLI."""
from alembic import context
from sqlalchemy import create_engine

from lab.config import load_settings
from lab.db import make_engine
from lab.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url") or load_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = config.attributes.get("connection")
    if engine is None:
        settings = load_settings()
        engine = make_engine(config.get_main_option("sqlalchemy.url") or settings.database_url, settings.database_schema)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
