"""auth_alerts: phone sign-in (codes, sessions), operator alerts, the owner's sign-in number

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('businesses') as b:
        b.add_column(sa.Column('owner_phone', sa.String(length=20), nullable=False, server_default=''))
        b.create_index('ix_businesses_owner_phone', ['owner_phone'])
    conn = op.get_bind()  # existing owners can sign in with the owner number already in their profile
    import json
    rows = conn.execute(sa.text('SELECT id, settings FROM businesses')).fetchall()
    for bid, settings in rows:
        data = json.loads(settings) if isinstance(settings, str) else (settings or {})
        phone = ((data.get('profile') or {}).get('owner_phone') or '')[:20]
        if phone:
            conn.execute(sa.text('UPDATE businesses SET owner_phone = :p WHERE id = :i'), {'p': phone, 'i': bid})
    op.create_table('otp_codes',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=False, server_default=''),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('otp_codes') as b:
        b.create_index('ix_otp_codes_phone', ['phone'])
    op.create_table('owner_sessions',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('business_id', sa.String(length=32), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('device', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name='fk_owner_sessions_business', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_owner_sessions_token'))
    with op.batch_alter_table('owner_sessions') as b:
        b.create_index('ix_owner_sessions_business_id', ['business_id'])
    op.create_table('alerts',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('level', sa.String(length=10), nullable=False, server_default='warn'),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('detail', sa.Text(), nullable=False, server_default=''),
        sa.Column('count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('alerts') as b:
        b.create_index('ix_alerts_key', ['key'])


def downgrade() -> None:
    op.drop_table('alerts')
    op.drop_table('owner_sessions')
    op.drop_table('otp_codes')
    with op.batch_alter_table('businesses') as b:
        b.drop_index('ix_businesses_owner_phone')
        b.drop_column('owner_phone')
