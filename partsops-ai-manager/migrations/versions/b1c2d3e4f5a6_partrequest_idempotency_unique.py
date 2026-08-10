"""unique (tenant_id, idempotency_key) on partrequest when key present

Revision ID: b1c2d3e4f5a6
Revises: a9e4f1b2c3d0
Create Date: 2026-08-11

"""
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a9e4f1b2c3d0"
branch_labels = None
depends_on = None


def upgrade():
    # Partial unique index: multiple NULL keys remain allowed.
    # SQLite + PostgreSQL both support WHERE on unique indexes.
    op.create_index(
        "uq_partrequest_tenant_idempotency_key",
        "partrequest",
        ["tenant_id", "idempotency_key"],
        unique=True,
        sqlite_where="idempotency_key IS NOT NULL",
        postgresql_where="idempotency_key IS NOT NULL",
    )


def downgrade():
    op.drop_index("uq_partrequest_tenant_idempotency_key", table_name="partrequest")
