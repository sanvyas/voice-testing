from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from lab import db
from lab.config import load_settings
from lab.models import Base


def test_models_match_migrations(env):
    """Fails when someone changes models.py without adding a migration."""
    db.init_db(load_settings())
    try:
        with db.get_engine().connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
        assert diff == [], diff
    finally:
        db.dispose_db()


def test_migration_is_idempotent(env):
    settings = load_settings()
    db.init_db(settings)
    db.dispose_db()
    db.init_db(settings)  # second boot must be a no-op
    try:
        assert {"prompts", "conversations", "eval_results", "alembic_version"} <= set(inspect(db.get_engine()).get_table_names())
    finally:
        db.dispose_db()


def test_upgrade_keeps_existing_rows(env):
    """0001 -> 0002 on a database that already holds conversations (NOT NULL columns need defaults)."""
    from alembic import command
    from sqlalchemy import text

    settings = load_settings()
    engine = db.make_engine(settings.database_url)
    cfg = db._alembic_config(settings.database_url)
    cfg.attributes["connection"] = engine
    command.upgrade(cfg, "0001")
    with engine.begin() as c:
        c.execute(text("INSERT INTO conversations (id, source, status, title, mood, prompt_label, rendered_prompt, variables, scenario_snapshot, evalset_snapshot, gen_config, provider, model, attempts, generated, verdict_reason, created_at) "
                       "VALUES ('old1','simulated','completed','old','sad','p v1','x','{}','{}','{}','{}','','',0,true,'',CURRENT_TIMESTAMP)"))
    command.upgrade(cfg, "head")
    with engine.connect() as c:
        row = c.execute(text("SELECT client, user_ref, environment, api_key_id FROM conversations WHERE id='old1'")).one()
    assert tuple(row) == ("", "", "", None)
    command.downgrade(cfg, "0001")  # and back, without error
    engine.dispose()


import os as _os

import pytest as _pytest


@_pytest.mark.skipif(not _os.getenv("TEST_DATABASE_URL"), reason="needs a Postgres server (TEST_DATABASE_URL)")
def test_lab_lives_in_its_own_schema_and_cannot_touch_another_app(env):
    """Rehearsal of sharing a database (e.g. Supabase) with another app that has same-named tables."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text
    import main
    from lab.config import normalize_database_url

    admin_url = normalize_database_url(_os.environ["TEST_DATABASE_URL"])
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP OWNED BY voice_lab_t CASCADE")) if c.execute(text("select 1 from pg_roles where rolname='voice_lab_t'")).first() else None
        c.execute(text("DROP ROLE IF EXISTS voice_lab_t"))
        c.execute(text("DROP SCHEMA IF EXISTS vl CASCADE"))
        c.execute(text("CREATE TABLE public.conversations (id serial primary key, owner text)"))   # the OTHER app's table
        c.execute(text("INSERT INTO public.conversations (owner) VALUES ('saathi-user')"))
        c.execute(text("CREATE ROLE voice_lab_t LOGIN PASSWORD 'pw' NOSUPERUSER NOCREATEDB NOCREATEROLE"))
        c.execute(text("CREATE SCHEMA vl AUTHORIZATION voice_lab_t"))
        c.execute(text("ALTER ROLE voice_lab_t SET search_path = vl"))
    role_url = admin_url.replace("postgres@", "voice_lab_t:pw@", 1)
    env.setenv("DATABASE_URL", role_url)
    env.setenv("DATABASE_SCHEMA", "vl")
    with TestClient(main.app) as client:
        assert client.get("/api/lab/prompts").status_code == 200 and len(client.get("/api/lab/scenarios").json()) == 8
    with admin.connect() as c:
        cols = [r[0] for r in c.execute(text("select column_name from information_schema.columns where table_schema='public' and table_name='conversations' order by ordinal_position"))]
        assert cols == ["id", "owner"]                                                   # the other app's table is untouched
        assert c.execute(text("select count(*) from public.conversations")).scalar() == 1
        assert c.execute(text("select count(*) from information_schema.tables where table_schema='public' and table_name in ('prompts','turns','alembic_version')")).scalar() == 0
        mine = {r[0] for r in c.execute(text("select table_name from information_schema.tables where table_schema='vl'"))}
        assert {"conversations", "prompts", "alembic_version"} <= mine                    # everything of ours is in our schema
    role = create_engine(role_url)
    with role.connect() as c:
        with _pytest.raises(Exception, match="permission denied"):
            c.execute(text("select * from public.conversations")).all()                  # and our role cannot read theirs
    role.dispose(); admin.dispose()
