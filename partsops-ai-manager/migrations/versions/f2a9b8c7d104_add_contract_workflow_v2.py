"""add contract workflow v2 state and events

Revision ID: f2a9b8c7d104
Revises: e7b2c4d9a013
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "f2a9b8c7d104"
down_revision = "e7b2c4d9a013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    string = sqlmodel.sql.sqltypes.AutoString()
    op.create_table(
        "contractworkflowstate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("workflow_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("contract_ref", string, nullable=False),
        sa.Column("current_stage", string, nullable=False),
        sa.Column("current_stage_index", sa.Integer(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column("blocking_code", string, nullable=True),
        sa.Column("blocking_reason", string, nullable=True),
        sa.Column("updated_by", string, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contractworkflowstate_tenant_id", "contractworkflowstate", ["tenant_id"])
    op.create_index("ix_contractworkflowstate_workflow_id", "contractworkflowstate", ["workflow_id"], unique=True)
    op.create_index("ix_contractworkflowstate_request_id", "contractworkflowstate", ["request_id"], unique=True)
    op.create_index("ix_contractworkflowstate_contract_ref", "contractworkflowstate", ["contract_ref"])
    op.create_index("ix_contractworkflowstate_current_stage", "contractworkflowstate", ["current_stage"])

    op.create_table(
        "contractworkflowevent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("workflow_event_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("from_stage", string, nullable=True),
        sa.Column("to_stage", string, nullable=False),
        sa.Column("actor_id", string, nullable=False),
        sa.Column("reason", string, nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("violations_json", string, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contractworkflowevent_tenant_id", "contractworkflowevent", ["tenant_id"])
    op.create_index("ix_contractworkflowevent_workflow_event_id", "contractworkflowevent", ["workflow_event_id"], unique=True)
    op.create_index("ix_contractworkflowevent_request_id", "contractworkflowevent", ["request_id"])


def downgrade() -> None:
    op.drop_table("contractworkflowevent")
    op.drop_table("contractworkflowstate")
