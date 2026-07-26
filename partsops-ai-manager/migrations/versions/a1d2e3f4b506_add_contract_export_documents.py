"""add contract export document artifact fields

Revision ID: a1d2e3f4b506
Revises: f2a9b8c7d104
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "a1d2e3f4b506"
down_revision = "f2a9b8c7d104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    string = sqlmodel.sql.sqltypes.AutoString()
    op.add_column("contractexport", sa.Column("internal_registry_path", string, nullable=True))
    op.add_column("contractexport", sa.Column("internal_registry_sha256", string, nullable=True))
    op.add_column("contractexport", sa.Column("client_document_path", string, nullable=True))
    op.add_column("contractexport", sa.Column("client_document_sha256", string, nullable=True))


def downgrade() -> None:
    op.drop_column("contractexport", "client_document_sha256")
    op.drop_column("contractexport", "client_document_path")
    op.drop_column("contractexport", "internal_registry_sha256")
    op.drop_column("contractexport", "internal_registry_path")
