"""add catalog oem_number and brand indexes for matcher prefilter

Revision ID: 7c2e9a1b0d40
Revises: 6a1f4e8b2c70
Create Date: 2026-08-09

"""
from __future__ import annotations

from alembic import op


revision = "7c2e9a1b0d40"
down_revision = "6a1f4e8b2c70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite + Postgres compatible single-column indexes (composite optional later)
    op.create_index(
        "ix_suppliercatalogitem_oem_number",
        "suppliercatalogitem",
        ["oem_number"],
        unique=False,
    )
    op.create_index(
        "ix_suppliercatalogitem_brand",
        "suppliercatalogitem",
        ["brand"],
        unique=False,
    )
    # Composite helps tenant-scoped OEM lookup on Postgres
    op.create_index(
        "ix_suppliercatalogitem_tenant_oem",
        "suppliercatalogitem",
        ["tenant_id", "oem_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_suppliercatalogitem_tenant_oem", table_name="suppliercatalogitem")
    op.drop_index("ix_suppliercatalogitem_brand", table_name="suppliercatalogitem")
    op.drop_index("ix_suppliercatalogitem_oem_number", table_name="suppliercatalogitem")
