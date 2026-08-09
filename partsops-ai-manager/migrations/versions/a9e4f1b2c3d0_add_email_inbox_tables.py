"""add email inbox tables for RFQ inbound mail

Revision ID: a9e4f1b2c3d0
Revises: 7c2e9a1b0d40
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "a9e4f1b2c3d0"
down_revision = "7c2e9a1b0d40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_inbox_configs",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("org_slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("address", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("auto_ingest", sa.Boolean(), nullable=False),
        sa.Column("default_priority", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("allowed_senders_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("default_mapping_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_slug", name="uq_email_inbox_org_slug"),
        sa.UniqueConstraint("address", name="uq_email_inbox_address"),
    )
    op.create_index("ix_email_inbox_configs_tenant_id", "email_inbox_configs", ["tenant_id"])
    op.create_index("ix_email_inbox_configs_org_slug", "email_inbox_configs", ["org_slug"])

    op.create_table(
        "email_messages",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider_message_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("from_masked", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("to_address", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("subject", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("raw_storage_uri", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("raw_sha256", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("body_masked_excerpt", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("request_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("rejection_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("attachment_artifact_ids_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("auth_results_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_message_id",
            name="uq_email_messages_tenant_message_id",
        ),
    )
    op.create_index("ix_email_messages_tenant_id", "email_messages", ["tenant_id"])
    op.create_index("ix_email_messages_provider_message_id", "email_messages", ["provider_message_id"])
    op.create_index("ix_email_messages_received_at", "email_messages", ["received_at"])
    op.create_index("ix_email_messages_status", "email_messages", ["status"])
    op.create_index("ix_email_messages_request_id", "email_messages", ["request_id"])


def downgrade():
    op.drop_index("ix_email_messages_request_id", table_name="email_messages")
    op.drop_index("ix_email_messages_status", table_name="email_messages")
    op.drop_index("ix_email_messages_received_at", table_name="email_messages")
    op.drop_index("ix_email_messages_provider_message_id", table_name="email_messages")
    op.drop_index("ix_email_messages_tenant_id", table_name="email_messages")
    op.drop_table("email_messages")

    op.drop_index("ix_email_inbox_configs_org_slug", table_name="email_inbox_configs")
    op.drop_index("ix_email_inbox_configs_tenant_id", table_name="email_inbox_configs")
    op.drop_table("email_inbox_configs")
