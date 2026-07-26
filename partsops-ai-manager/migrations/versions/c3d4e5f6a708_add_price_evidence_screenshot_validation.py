"""add price evidence screenshot validation fields

Revision ID: c3d4e5f6a708
Revises: b2c3d4e5f607
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "c3d4e5f6a708"
down_revision = "b2c3d4e5f607"
branch_labels = None
depends_on = None


def upgrade() -> None:
    string = sqlmodel.sql.sqltypes.AutoString()
    op.add_column("priceevidence", sa.Column("screenshot_readability_status", string, nullable=False, server_default="unknown"))
    op.add_column("priceevidence", sa.Column("screenshot_completeness_status", string, nullable=False, server_default="partial"))
    op.add_column("priceevidence", sa.Column("screenshot_validation_json", string, nullable=True))


def downgrade() -> None:
    op.drop_column("priceevidence", "screenshot_validation_json")
    op.drop_column("priceevidence", "screenshot_completeness_status")
    op.drop_column("priceevidence", "screenshot_readability_status")
