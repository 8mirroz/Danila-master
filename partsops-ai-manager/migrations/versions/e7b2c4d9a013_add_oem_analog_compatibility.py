"""add oem analog compatibility tables

Revision ID: e7b2c4d9a013
Revises: d4f6a8c2b901
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "e7b2c4d9a013"
down_revision = "d4f6a8c2b901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    string = sqlmodel.sql.sqltypes.AutoString()

    op.create_table(
        "oemcandidate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("candidate_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("position_id", string, nullable=False),
        sa.Column("oem_number", string, nullable=False),
        sa.Column("manufacturer", string, nullable=True),
        sa.Column("source", string, nullable=False),
        sa.Column("source_url", string, nullable=True),
        sa.Column("evidence_ref", string, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("lifecycle_status", string, nullable=False),
        sa.Column("previous_article", string, nullable=True),
        sa.Column("replacement_article", string, nullable=True),
        sa.Column("verification_status", string, nullable=False),
        sa.Column("reviewed_by", string, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", string, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_oemcandidate_tenant_id", "oemcandidate", ["tenant_id"])
    op.create_index("ix_oemcandidate_candidate_id", "oemcandidate", ["candidate_id"], unique=True)
    op.create_index("ix_oemcandidate_request_id", "oemcandidate", ["request_id"])
    op.create_index("ix_oemcandidate_position_id", "oemcandidate", ["position_id"])
    op.create_index("ix_oemcandidate_oem_number", "oemcandidate", ["oem_number"])

    op.create_table(
        "analogcandidate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("candidate_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("position_id", string, nullable=False),
        sa.Column("oem_candidate_id", string, nullable=True),
        sa.Column("article", string, nullable=False),
        sa.Column("brand", string, nullable=False),
        sa.Column("manufacturer", string, nullable=True),
        sa.Column("source", string, nullable=False),
        sa.Column("source_url", string, nullable=True),
        sa.Column("cross_reference_source", string, nullable=True),
        sa.Column("interchange_type", string, nullable=False),
        sa.Column("lifecycle_status", string, nullable=False),
        sa.Column("previous_article", string, nullable=True),
        sa.Column("replacement_article", string, nullable=True),
        sa.Column("independent_confirmations", sa.Integer(), nullable=False),
        sa.Column("compatibility_score", sa.Integer(), nullable=False),
        sa.Column("evidence_score", sa.Integer(), nullable=False),
        sa.Column("counterfeit_risk", string, nullable=False),
        sa.Column("obsolete_article_risk", string, nullable=False),
        sa.Column("manual_review_status", string, nullable=False),
        sa.Column("rejection_reason", string, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_analogcandidate_tenant_id", "analogcandidate", ["tenant_id"])
    op.create_index("ix_analogcandidate_candidate_id", "analogcandidate", ["candidate_id"], unique=True)
    op.create_index("ix_analogcandidate_request_id", "analogcandidate", ["request_id"])
    op.create_index("ix_analogcandidate_position_id", "analogcandidate", ["position_id"])
    op.create_index("ix_analogcandidate_oem_candidate_id", "analogcandidate", ["oem_candidate_id"])
    op.create_index("ix_analogcandidate_article", "analogcandidate", ["article"])

    op.create_table(
        "compatibilityevidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("evidence_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("position_id", string, nullable=False),
        sa.Column("candidate_type", string, nullable=False),
        sa.Column("candidate_id", string, nullable=False),
        sa.Column("evidence_type", string, nullable=False),
        sa.Column("source", string, nullable=False),
        sa.Column("source_url", string, nullable=True),
        sa.Column("score_points", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("evidence_ref", string, nullable=True),
        sa.Column("evidence_hash", string, nullable=True),
        sa.Column("readability_status", string, nullable=False),
        sa.Column("completeness_status", string, nullable=False),
        sa.Column("freshness_status", string, nullable=False),
        sa.Column("created_by", string, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_compatibilityevidence_tenant_id", "compatibilityevidence", ["tenant_id"])
    op.create_index("ix_compatibilityevidence_evidence_id", "compatibilityevidence", ["evidence_id"], unique=True)
    op.create_index("ix_compatibilityevidence_request_id", "compatibilityevidence", ["request_id"])
    op.create_index("ix_compatibilityevidence_position_id", "compatibilityevidence", ["position_id"])
    op.create_index("ix_compatibilityevidence_candidate_id", "compatibilityevidence", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("compatibilityevidence")
    op.drop_table("analogcandidate")
    op.drop_table("oemcandidate")
