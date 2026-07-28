"""add durable pipeline run queue and replayable events"""

from alembic import op
import sqlalchemy as sa


revision = "9c5d7e1a2b34"
down_revision = "8b2c4d6e7f90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipelinerun",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("requested_lane", sa.String(), nullable=True),
        sa.Column("start_from", sa.String(), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("result_json", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("lease_owner", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for name, columns in (
        ("ix_pipelinerun_tenant_id", ["tenant_id"]),
        ("ix_pipelinerun_request_id", ["request_id"]),
        ("ix_pipelinerun_correlation_id", ["correlation_id"]),
        ("ix_pipelinerun_status", ["status"]),
        ("ix_pipelinerun_lease_owner", ["lease_owner"]),
    ):
        op.create_index(name, "pipelinerun", columns)
    op.create_table(
        "pipelinerunevent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("phase", sa.String(), nullable=True),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("payload_json", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for name, columns in (
        ("ix_pipelinerunevent_run_id", ["run_id"]),
        ("ix_pipelinerunevent_tenant_id", ["tenant_id"]),
    ):
        op.create_index(name, "pipelinerunevent", columns)


def downgrade() -> None:
    for name in ("ix_pipelinerunevent_tenant_id", "ix_pipelinerunevent_run_id"):
        op.drop_index(name, table_name="pipelinerunevent", if_exists=True)
    op.drop_table("pipelinerunevent")
    for name in ("ix_pipelinerun_lease_owner", "ix_pipelinerun_status", "ix_pipelinerun_correlation_id", "ix_pipelinerun_request_id", "ix_pipelinerun_tenant_id"):
        op.drop_index(name, table_name="pipelinerun", if_exists=True)
    op.drop_table("pipelinerun")
