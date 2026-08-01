"""add manual correction position attribution

Revision ID: 6a1f4e8b2c70
Revises: 5e9a2c3d6f40
"""

from alembic import op
import sqlalchemy as sa


revision = "6a1f4e8b2c70"
down_revision = "5e9a2c3d6f40"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("goldensample", sa.Column("corrected_position_indexes_json", sa.String(), nullable=True))


def downgrade():
    op.drop_column("goldensample", "corrected_position_indexes_json")
