"""add contract operations evidence tables"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "8a4c2d9e1f70"
down_revision = "50ece6030d5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    string = sqlmodel.sql.sqltypes.AutoString()
    op.create_table("contractposition",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("tenant_id", string, nullable=False),
        sa.Column("position_id", string, nullable=False), sa.Column("request_id", string, nullable=False),
        sa.Column("contract_ref", string, nullable=False), sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("part_number", string, nullable=False), sa.Column("description", string),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("selected_evidence_id", string),
        sa.Column("review_status", string, nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_contractposition_tenant_id", "contractposition", ["tenant_id"])
    op.create_index("ix_contractposition_position_id", "contractposition", ["position_id"], unique=True)
    op.create_index("ix_contractposition_request_id", "contractposition", ["request_id"])
    op.create_index("ix_contractposition_contract_ref", "contractposition", ["contract_ref"])
    op.create_table("priceevidence",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("tenant_id", string, nullable=False),
        sa.Column("evidence_id", string, nullable=False), sa.Column("request_id", string, nullable=False),
        sa.Column("position_id", string, nullable=False), sa.Column("source", string, nullable=False),
        sa.Column("price", sa.Float(), nullable=False), sa.Column("currency", string, nullable=False),
        sa.Column("source_url", string, nullable=False), sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("screenshot_ref", string, nullable=False), sa.Column("screenshot_sha256", string),
        sa.Column("adapter_run_id", string), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_priceevidence_tenant_id", "priceevidence", ["tenant_id"])
    op.create_index("ix_priceevidence_evidence_id", "priceevidence", ["evidence_id"], unique=True)
    op.create_index("ix_priceevidence_request_id", "priceevidence", ["request_id"])
    op.create_index("ix_priceevidence_position_id", "priceevidence", ["position_id"])
    op.create_table("contractexport",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("tenant_id", string, nullable=False),
        sa.Column("export_id", string, nullable=False), sa.Column("request_id", string, nullable=False),
        sa.Column("contract_ref", string, nullable=False), sa.Column("template_name", string, nullable=False),
        sa.Column("content_json", string, nullable=False), sa.Column("created_by", string, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("export_id"))
    op.create_index("ix_contractexport_tenant_id", "contractexport", ["tenant_id"])
    op.create_index("ix_contractexport_export_id", "contractexport", ["export_id"], unique=True)
    op.create_index("ix_contractexport_request_id", "contractexport", ["request_id"])
    op.create_index("ix_contractexport_contract_ref", "contractexport", ["contract_ref"])


def downgrade() -> None:
    op.drop_table("contractexport")
    op.drop_table("priceevidence")
    op.drop_table("contractposition")
