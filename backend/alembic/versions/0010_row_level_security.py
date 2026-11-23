"""row_level_security: a second lock on every table (Postgres only)

The app connects as the table owner, which row-level security does not apply to, so nothing changes for the app.
The public API roles (anon, authenticated) already have no access to this schema; RLS with no policy means that if a grant is ever added by
mistake, they still read and write nothing.

Revision ID: 0010
Revises: 0009
"""
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def _tables(bind):
    rows = bind.exec_driver_sql("SELECT tablename FROM pg_tables WHERE schemaname = current_schema() AND tablename <> 'alembic_version'").fetchall()
    return [r[0] for r in rows]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    for t in _tables(bind):
        op.execute(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    for t in _tables(bind):
        op.execute(f'ALTER TABLE "{t}" DISABLE ROW LEVEL SECURITY')
