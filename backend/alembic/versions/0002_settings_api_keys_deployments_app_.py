"""settings, api keys, deployments, app client fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01 11:04:15.307660
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('api_keys',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('environment', sa.String(length=20), nullable=False),
    sa.Column('prefix', sa.String(length=16), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_keys_key_hash'), ['key_hash'], unique=True)

    op.create_table('settings',
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('deployments',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('environment', sa.String(length=20), nullable=False),
    sa.Column('prompt_version_id', sa.String(length=32), nullable=False),
    sa.Column('variables', sa.JSON(), nullable=False),
    sa.Column('gen', sa.JSON(), nullable=False),
    sa.Column('note', sa.String(length=500), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['prompt_version_id'], ['prompt_versions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('deployments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deployments_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_deployments_environment'), ['environment'], unique=False)

    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client', sa.String(length=40), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('user_ref', sa.String(length=100), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('environment', sa.String(length=20), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('api_key_id', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('deployment_id', sa.String(length=32), nullable=True))
        batch_op.create_index(batch_op.f('ix_conversations_api_key_id'), ['api_key_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_environment'), ['environment'], unique=False)
        batch_op.create_foreign_key('fk_conversations_api_key', 'api_keys', ['api_key_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_conversations_deployment', 'deployments', ['deployment_id'], ['id'], ondelete='SET NULL')



def downgrade() -> None:
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_constraint('fk_conversations_deployment', type_='foreignkey')
        batch_op.drop_constraint('fk_conversations_api_key', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_conversations_environment'))
        batch_op.drop_index(batch_op.f('ix_conversations_api_key_id'))
        batch_op.drop_column('deployment_id')
        batch_op.drop_column('api_key_id')
        batch_op.drop_column('environment')
        batch_op.drop_column('user_ref')
        batch_op.drop_column('client')

    with op.batch_alter_table('deployments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deployments_environment'))
        batch_op.drop_index(batch_op.f('ix_deployments_created_at'))

    op.drop_table('deployments')
    op.drop_table('settings')
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_api_keys_key_hash'))

    op.drop_table('api_keys')
