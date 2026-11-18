"""wa_messages: the WhatsApp thread with each person (messages that really went out)

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('wa_messages',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('business_id', sa.String(length=32), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('call_id', sa.String(length=32), nullable=True),
        sa.Column('sender', sa.String(length=10), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('provider_id', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name='fk_wa_messages_business', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], name='fk_wa_messages_call', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('wa_messages') as b:
        b.create_index('ix_wa_messages_business_id', ['business_id'])
        b.create_index('ix_wa_messages_phone', ['phone'])
        b.create_index('ix_wa_messages_created_at', ['created_at'])


def downgrade() -> None:
    op.drop_table('wa_messages')
