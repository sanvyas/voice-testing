"""businesses: every contact, call, board item and audit entry belongs to one business

Revision ID: 0007
Revises: 0006
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

OWNED = ("contacts", "calls", "board_items")


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table('businesses',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=True),
        sa.Column('key_enc', sa.Text(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'))
    with op.batch_alter_table('businesses') as b:
        b.create_index('ix_businesses_phone_number', ['phone_number'])

    # The single business that used to be the whole product becomes the first business.
    settings = sa.table('settings', sa.column('key', sa.String), sa.column('value', sa.JSON))
    rows = {r.key: r.value for r in bind.execute(sa.select(settings.c.key, settings.c.value))}
    mine = {name: rows[f"assistant.{name}"] for name in ("profile", "knowledge", "budget", "dismissed") if f"assistant.{name}" in rows}
    profile = mine.get("profile") or {}
    phone = (rows.get("phone") or {}).get("number", "") or ""
    biz_id = uuid.uuid4().hex
    businesses = sa.table('businesses', sa.column('id'), sa.column('name'), sa.column('active'), sa.column('phone_number'), sa.column('settings', sa.JSON), sa.column('created_at', sa.DateTime(timezone=True)))
    has_data = bool(mine) or any(bind.execute(sa.text(f"SELECT 1 FROM {t} LIMIT 1")).first() for t in OWNED)
    if has_data:
        bind.execute(sa.insert(businesses).values(id=biz_id, name=(profile.get("business_name") or "My business")[:120], active=True,
                                                   phone_number=phone[:20], settings=mine, created_at=datetime.now(timezone.utc)))

    for table in OWNED:
        with op.batch_alter_table(table) as b:
            b.add_column(sa.Column('business_id', sa.String(length=32), nullable=True))
        if has_data:
            bind.execute(sa.text(f"UPDATE {table} SET business_id = :b"), {"b": biz_id})
        with op.batch_alter_table(table) as b:
            b.alter_column('business_id', existing_type=sa.String(length=32), nullable=False)
            b.create_index(f'ix_{table}_business_id', ['business_id'])
            b.create_foreign_key(f'fk_{table}_business', 'businesses', ['business_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('audit_entries') as b:
        b.add_column(sa.Column('business_id', sa.String(length=32), nullable=True))
        b.create_index('ix_audit_entries_business_id', ['business_id'])
        b.create_foreign_key('fk_audit_entries_business', 'businesses', ['business_id'], ['id'], ondelete='CASCADE')
    if has_data:
        bind.execute(sa.text("UPDATE audit_entries SET business_id = :b"), {"b": biz_id})

    # a phone number may belong to different businesses now (the old constraint is unnamed on SQLite, named by Postgres)
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table('contacts', naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}) as b:
            b.drop_constraint('uq_contacts_phone', type_='unique')
            b.create_unique_constraint('uq_contact_business_phone', ['business_id', 'phone'])
    else:
        for uc in sa.inspect(bind).get_unique_constraints('contacts'):
            if uc['column_names'] == ['phone']:
                op.drop_constraint(uc['name'], 'contacts', type_='unique')
        op.create_unique_constraint('uq_contact_business_phone', 'contacts', ['business_id', 'phone'])


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table('contacts') as b:
        b.drop_constraint('uq_contact_business_phone', type_='unique')
        b.create_unique_constraint('uq_contacts_phone', ['phone'])
    with op.batch_alter_table('audit_entries') as b:
        b.drop_constraint('fk_audit_entries_business', type_='foreignkey')
        b.drop_index('ix_audit_entries_business_id')
        b.drop_column('business_id')
    for table in OWNED:
        with op.batch_alter_table(table) as b:
            b.drop_constraint(f'fk_{table}_business', type_='foreignkey')
            b.drop_index(f'ix_{table}_business_id')
            b.drop_column('business_id')
    op.drop_table('businesses')
