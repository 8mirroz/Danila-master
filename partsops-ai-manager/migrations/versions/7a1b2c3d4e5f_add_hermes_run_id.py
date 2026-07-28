"""persist native Hermes run identifiers

Revision ID: 7a1b2c3d4e5f
Revises: f3b4c5d6e708
"""
from alembic import op
import sqlalchemy as sa

revision = "7a1b2c3d4e5f"
down_revision = "f3b4c5d6e708"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("copilot_runs", sa.Column("hermes_run_id", sa.String(), nullable=True))
    op.create_index("ix_copilot_runs_hermes_run_id", "copilot_runs", ["hermes_run_id"], unique=False)


def downgrade():
    op.drop_index("ix_copilot_runs_hermes_run_id", table_name="copilot_runs")
    op.drop_column("copilot_runs", "hermes_run_id")
