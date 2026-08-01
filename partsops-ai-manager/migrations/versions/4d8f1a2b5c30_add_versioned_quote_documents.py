"""add versioned commercial quote documents

Revision ID: 4d8f1a2b5c30
Revises: 3a7e9b1c4d20
"""

from alembic import op
import sqlalchemy as sa


revision = "4d8f1a2b5c30"
down_revision = "3a7e9b1c4d20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quotedocument",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_id"),
        sa.UniqueConstraint("organization_id", "request_id", name="uq_quote_document_org_request"),
    )
    op.create_index("ix_quotedocument_quote_id", "quotedocument", ["quote_id"], unique=True)
    op.create_index("ix_quotedocument_organization_id", "quotedocument", ["organization_id"])
    op.create_index("ix_quotedocument_request_id", "quotedocument", ["request_id"])
    op.create_index("ix_quotedocument_status", "quotedocument", ["status"])
    op.create_table(
        "quoteversion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("pricing_snapshot_json", sa.String(), nullable=False),
        sa.Column("selected_offer_snapshot_json", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_id", "version", name="uq_quote_version"),
    )
    op.create_index("ix_quoteversion_quote_id", "quoteversion", ["quote_id"])
    op.create_index("ix_quoteversion_organization_id", "quoteversion", ["organization_id"])


def downgrade():
    op.drop_index("ix_quoteversion_organization_id", table_name="quoteversion", if_exists=True)
    op.drop_index("ix_quoteversion_quote_id", table_name="quoteversion", if_exists=True)
    op.drop_table("quoteversion")
    op.drop_index("ix_quotedocument_status", table_name="quotedocument", if_exists=True)
    op.drop_index("ix_quotedocument_request_id", table_name="quotedocument", if_exists=True)
    op.drop_index("ix_quotedocument_organization_id", table_name="quotedocument", if_exists=True)
    op.drop_index("ix_quotedocument_quote_id", table_name="quotedocument", if_exists=True)
    op.drop_table("quotedocument")
