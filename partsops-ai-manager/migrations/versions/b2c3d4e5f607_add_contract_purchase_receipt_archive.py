"""add contract purchase receipt archive records

Revision ID: b2c3d4e5f607
Revises: a1d2e3f4b506
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "b2c3d4e5f607"
down_revision = "a1d2e3f4b506"
branch_labels = None
depends_on = None


def upgrade() -> None:
    string = sqlmodel.sql.sqltypes.AutoString()
    op.create_table(
        "contractpurchaserecord",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("purchase_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("authorization_id", string, nullable=False),
        sa.Column("supplier_ref", string, nullable=False),
        sa.Column("ordered_by", string, nullable=False),
        sa.Column("ordered_at", sa.DateTime(), nullable=False),
        sa.Column("amount_total", sa.Float(), nullable=False),
        sa.Column("currency", string, nullable=False),
        sa.Column("evidence_ref", string, nullable=True),
        sa.Column("status", string, nullable=False),
        sa.Column("comment", string, nullable=True),
    )
    op.create_index("ix_contractpurchaserecord_tenant_id", "contractpurchaserecord", ["tenant_id"])
    op.create_index("ix_contractpurchaserecord_purchase_id", "contractpurchaserecord", ["purchase_id"], unique=True)
    op.create_index("ix_contractpurchaserecord_request_id", "contractpurchaserecord", ["request_id"])
    op.create_index("ix_contractpurchaserecord_authorization_id", "contractpurchaserecord", ["authorization_id"])

    op.create_table(
        "contractreceiptverification",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("receipt_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("purchase_id", string, nullable=False),
        sa.Column("verified_by", string, nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=False),
        sa.Column("evidence_ref", string, nullable=False),
        sa.Column("received_quantity", sa.Integer(), nullable=False),
        sa.Column("status", string, nullable=False),
        sa.Column("discrepancy_note", string, nullable=True),
    )
    op.create_index("ix_contractreceiptverification_tenant_id", "contractreceiptverification", ["tenant_id"])
    op.create_index("ix_contractreceiptverification_receipt_id", "contractreceiptverification", ["receipt_id"], unique=True)
    op.create_index("ix_contractreceiptverification_request_id", "contractreceiptverification", ["request_id"])
    op.create_index("ix_contractreceiptverification_purchase_id", "contractreceiptverification", ["purchase_id"])

    op.create_table(
        "contractarchiverecord",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("archive_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("receipt_id", string, nullable=False),
        sa.Column("archived_by", string, nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=False),
        sa.Column("archive_ref", string, nullable=False),
        sa.Column("registry_hash", string, nullable=True),
        sa.Column("status", string, nullable=False),
        sa.Column("comment", string, nullable=True),
    )
    op.create_index("ix_contractarchiverecord_tenant_id", "contractarchiverecord", ["tenant_id"])
    op.create_index("ix_contractarchiverecord_archive_id", "contractarchiverecord", ["archive_id"], unique=True)
    op.create_index("ix_contractarchiverecord_request_id", "contractarchiverecord", ["request_id"])
    op.create_index("ix_contractarchiverecord_receipt_id", "contractarchiverecord", ["receipt_id"])


def downgrade() -> None:
    op.drop_table("contractarchiverecord")
    op.drop_table("contractreceiptverification")
    op.drop_table("contractpurchaserecord")
