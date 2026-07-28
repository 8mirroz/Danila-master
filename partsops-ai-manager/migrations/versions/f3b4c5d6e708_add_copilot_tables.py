"""add copilot tables for Hermes assistant

Revision ID: f3b4c5d6e708
Revises: d4f6a8c2b901
Create Date: 2026-07-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision = 'f3b4c5d6e708'
down_revision = 'c3d4e5f6a708'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'copilot_conversations',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tenant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('owner_fingerprint', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('hermes_session_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_copilot_conversations_tenant_id', 'copilot_conversations', ['tenant_id'], unique=False)
    op.create_index('ix_copilot_conversations_expires_at', 'copilot_conversations', ['expires_at'], unique=False)

    op.create_table(
        'copilot_messages',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('conversation_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('masked_content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('sources_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['copilot_conversations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_copilot_messages_conversation_id', 'copilot_messages', ['conversation_id'], unique=False)

    op.create_table(
        'copilot_runs',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('conversation_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('correlation_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('context_ref_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['copilot_conversations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_copilot_runs_conversation_id', 'copilot_runs', ['conversation_id'], unique=False)
    op.create_index('ix_copilot_runs_correlation_id', 'copilot_runs', ['correlation_id'], unique=False)


def downgrade():
    op.drop_index('ix_copilot_runs_correlation_id', table_name='copilot_runs')
    op.drop_index('ix_copilot_runs_conversation_id', table_name='copilot_runs')
    op.drop_table('copilot_runs')

    op.drop_index('ix_copilot_messages_conversation_id', table_name='copilot_messages')
    op.drop_table('copilot_messages')

    op.drop_index('ix_copilot_conversations_expires_at', table_name='copilot_conversations')
    op.drop_index('ix_copilot_conversations_tenant_id', table_name='copilot_conversations')
    op.drop_table('copilot_conversations')
