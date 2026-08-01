"""add contract control v2 tables and evidence gates

Revision ID: d4f6a8c2b901
Revises: b7c9e2d4a611
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "d4f6a8c2b901"
down_revision = "b7c9e2d4a611"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    string = sqlmodel.sql.sqltypes.AutoString()

    position_columns = _columns("contractposition")
    with op.batch_alter_table("contractposition") as batch:
        if "position_uuid" not in position_columns:
            batch.add_column(sa.Column("position_uuid", string, nullable=True))
        if "position_version" not in position_columns:
            batch.add_column(sa.Column("position_version", sa.Integer(), nullable=False, server_default="1"))
        if "vehicle_identity_status" not in position_columns:
            batch.add_column(sa.Column("vehicle_identity_status", string, nullable=False, server_default="unknown"))
        if "vehicle_data_source" not in position_columns:
            batch.add_column(sa.Column("vehicle_data_source", string, nullable=True))
        if "vin_checked_at" not in position_columns:
            batch.add_column(sa.Column("vin_checked_at", sa.DateTime(), nullable=True))
        if "criticality" not in position_columns:
            batch.add_column(sa.Column("criticality", string, nullable=False, server_default="Medium"))
        if "delivery_deadline_at" not in position_columns:
            batch.add_column(sa.Column("delivery_deadline_at", sa.DateTime(), nullable=True))
        if "max_delivery_days" not in position_columns:
            batch.add_column(sa.Column("max_delivery_days", sa.Integer(), nullable=True))
        if "safety_related" not in position_columns:
            batch.add_column(sa.Column("safety_related", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        if "warranty_impact" not in position_columns:
            batch.add_column(sa.Column("warranty_impact", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        if "requirement_id" not in position_columns:
            batch.add_column(sa.Column("requirement_id", string, nullable=True))
        if "completeness_status" not in position_columns:
            batch.add_column(sa.Column("completeness_status", string, nullable=False, server_default="partial"))
        if "blocking_status" not in position_columns:
            batch.add_column(sa.Column("blocking_status", string, nullable=False, server_default="blocked"))
        if "blocking_error_code" not in position_columns:
            batch.add_column(sa.Column("blocking_error_code", string, nullable=True))
        if "change_reason" not in position_columns:
            batch.add_column(sa.Column("change_reason", string, nullable=True))
        if "selected_reason" not in position_columns:
            batch.add_column(sa.Column("selected_reason", string, nullable=True))
        if "calculation_json" not in position_columns:
            batch.add_column(sa.Column("calculation_json", string, nullable=True))

    evidence_columns = _columns("priceevidence")
    with op.batch_alter_table("priceevidence") as batch:
        if "freshness_ttl_hours" not in evidence_columns:
            batch.add_column(sa.Column("freshness_ttl_hours", sa.Integer(), nullable=False, server_default="24"))
        if "expires_at" not in evidence_columns:
            batch.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
        if "availability_status" not in evidence_columns:
            batch.add_column(sa.Column("availability_status", string, nullable=False, server_default="available"))
        if "package_quantity" not in evidence_columns:
            batch.add_column(sa.Column("package_quantity", sa.Integer(), nullable=False, server_default="1"))
        if "unit" not in evidence_columns:
            batch.add_column(sa.Column("unit", string, nullable=False, server_default="piece"))
        if "condition" not in evidence_columns:
            batch.add_column(sa.Column("condition", string, nullable=False, server_default="new"))
        if "vat_included" not in evidence_columns:
            batch.add_column(sa.Column("vat_included", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        if "available_quantity" not in evidence_columns:
            batch.add_column(sa.Column("available_quantity", sa.Integer(), nullable=True))
        if "warehouse" not in evidence_columns:
            batch.add_column(sa.Column("warehouse", string, nullable=True))
        if "delivery_region" not in evidence_columns:
            batch.add_column(sa.Column("delivery_region", string, nullable=True))
        if "delivery_eta_days" not in evidence_columns:
            batch.add_column(sa.Column("delivery_eta_days", sa.Integer(), nullable=True))
        if "order_status" not in evidence_columns:
            batch.add_column(sa.Column("order_status", string, nullable=False, server_default="observed"))
        if "html_sha256" not in evidence_columns:
            batch.add_column(sa.Column("html_sha256", string, nullable=True))
        if "parser_version" not in evidence_columns:
            batch.add_column(sa.Column("parser_version", string, nullable=True))
        if "retry_count" not in evidence_columns:
            batch.add_column(sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
        if "unavailable_reason" not in evidence_columns:
            batch.add_column(sa.Column("unavailable_reason", string, nullable=True))
        if "comparability_status" not in evidence_columns:
            batch.add_column(sa.Column("comparability_status", string, nullable=False, server_default="REQUIRES_REVIEW"))
        if "evidence_status" not in evidence_columns:
            batch.add_column(sa.Column("evidence_status", string, nullable=False, server_default="pending"))

    export_columns = _columns("contractexport")
    with op.batch_alter_table("contractexport") as batch:
        if "document_version" not in export_columns:
            batch.add_column(sa.Column("document_version", string, nullable=False, server_default="v1.0"))
        if "registry_hash" not in export_columns:
            batch.add_column(sa.Column("registry_hash", string, nullable=True))
        if "diff_status" not in export_columns:
            batch.add_column(sa.Column("diff_status", string, nullable=False, server_default="validated"))

    op.create_table(
        "contractauditrun",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("audit_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("contract_ref", string, nullable=False),
        sa.Column("input_documents_json", string, nullable=False),
        sa.Column("existing_elements_json", string, nullable=False),
        sa.Column("status", string, nullable=False),
        sa.Column("unresolved_critical_count", sa.Integer(), nullable=False),
        sa.Column("created_by", string, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_contractauditrun_tenant_id", "contractauditrun", ["tenant_id"])
    op.create_index("ix_contractauditrun_audit_id", "contractauditrun", ["audit_id"], unique=True)
    op.create_index("ix_contractauditrun_request_id", "contractauditrun", ["request_id"])
    op.create_index("ix_contractauditrun_contract_ref", "contractauditrun", ["contract_ref"])

    op.create_table(
        "contractrequirement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("requirement_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("contract_ref", string, nullable=False),
        sa.Column("source", string, nullable=False),
        sa.Column("clause", string, nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("summary", string, nullable=False),
        sa.Column("exact_fragment", string, nullable=True),
        sa.Column("requirement_type", string, nullable=False),
        sa.Column("object_scope", string, nullable=False),
        sa.Column("applies_when", string, nullable=True),
        sa.Column("responsible", string, nullable=False),
        sa.Column("required_evidence", string, nullable=False),
        sa.Column("criticality", string, nullable=False),
        sa.Column("coverage_status", string, nullable=False),
        sa.Column("implementation_element", string, nullable=True),
        sa.Column("comment", string, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contractrequirement_tenant_id", "contractrequirement", ["tenant_id"])
    op.create_index("ix_contractrequirement_requirement_id", "contractrequirement", ["requirement_id"], unique=True)
    op.create_index("ix_contractrequirement_request_id", "contractrequirement", ["request_id"])
    op.create_index("ix_contractrequirement_contract_ref", "contractrequirement", ["contract_ref"])

    op.create_table(
        "requirementcoverage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("coverage_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("requirement_id", string, nullable=False),
        sa.Column("has_data", sa.Boolean(), nullable=False),
        sa.Column("has_check", sa.Boolean(), nullable=False),
        sa.Column("has_evidence", sa.Boolean(), nullable=False),
        sa.Column("has_responsible", sa.Boolean(), nullable=False),
        sa.Column("has_workflow_gate", sa.Boolean(), nullable=False),
        sa.Column("has_test", sa.Boolean(), nullable=False),
        sa.Column("export_covered", sa.Boolean(), nullable=False),
        sa.Column("status", string, nullable=False),
        sa.Column("notes", string, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_requirementcoverage_tenant_id", "requirementcoverage", ["tenant_id"])
    op.create_index("ix_requirementcoverage_coverage_id", "requirementcoverage", ["coverage_id"], unique=True)
    op.create_index("ix_requirementcoverage_request_id", "requirementcoverage", ["request_id"])
    op.create_index("ix_requirementcoverage_requirement_id", "requirementcoverage", ["requirement_id"])

    op.create_table(
        "contractgap",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("gap_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("requirement_id", string, nullable=True),
        sa.Column("category", string, nullable=False),
        sa.Column("description", string, nullable=False),
        sa.Column("source", string, nullable=False),
        sa.Column("risk", string, nullable=False),
        sa.Column("probability", string, nullable=False),
        sa.Column("impact", string, nullable=False),
        sa.Column("priority", string, nullable=False),
        sa.Column("proposed_change", string, nullable=False),
        sa.Column("affected_tables", string, nullable=False),
        sa.Column("affected_workflow_statuses", string, nullable=False),
        sa.Column("required_tests", string, nullable=False),
        sa.Column("closure_criteria", string, nullable=False),
        sa.Column("status", string, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_contractgap_tenant_id", "contractgap", ["tenant_id"])
    op.create_index("ix_contractgap_gap_id", "contractgap", ["gap_id"], unique=True)
    op.create_index("ix_contractgap_request_id", "contractgap", ["request_id"])
    op.create_index("ix_contractgap_requirement_id", "contractgap", ["requirement_id"])

    op.create_table(
        "adaptationdecisionrecord",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("adr_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("problem", string, nullable=False),
        sa.Column("requirement_id", string, nullable=True),
        sa.Column("current_state", string, nullable=False),
        sa.Column("decision", string, nullable=False),
        sa.Column("rationale", string, nullable=False),
        sa.Column("alternatives", string, nullable=False),
        sa.Column("affected_components", string, nullable=False),
        sa.Column("change_risk", string, nullable=False),
        sa.Column("migration", string, nullable=False),
        sa.Column("tests", string, nullable=False),
        sa.Column("rollback", string, nullable=False),
        sa.Column("created_by", string, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_adaptationdecisionrecord_tenant_id", "adaptationdecisionrecord", ["tenant_id"])
    op.create_index("ix_adaptationdecisionrecord_adr_id", "adaptationdecisionrecord", ["adr_id"], unique=True)
    op.create_index("ix_adaptationdecisionrecord_request_id", "adaptationdecisionrecord", ["request_id"])
    op.create_index("ix_adaptationdecisionrecord_requirement_id", "adaptationdecisionrecord", ["requirement_id"])

    op.create_table(
        "contractexceptionrecord",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("exception_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("position_id", string, nullable=True),
        sa.Column("code", string, nullable=False),
        sa.Column("severity", string, nullable=False),
        sa.Column("description", string, nullable=False),
        sa.Column("evidence_ref", string, nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("owner", string, nullable=False),
        sa.Column("escalation_due_at", sa.DateTime(), nullable=True),
        sa.Column("resolution", string, nullable=True),
        sa.Column("export_impact", string, nullable=False),
        sa.Column("status", string, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_contractexceptionrecord_tenant_id", "contractexceptionrecord", ["tenant_id"])
    op.create_index("ix_contractexceptionrecord_exception_id", "contractexceptionrecord", ["exception_id"], unique=True)
    op.create_index("ix_contractexceptionrecord_request_id", "contractexceptionrecord", ["request_id"])
    op.create_index("ix_contractexceptionrecord_position_id", "contractexceptionrecord", ["position_id"])
    op.create_index("ix_contractexceptionrecord_code", "contractexceptionrecord", ["code"])

    op.create_table(
        "clientapproval",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("approval_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("export_id", string, nullable=False),
        sa.Column("approved_by", string, nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
        sa.Column("evidence_ref", string, nullable=True),
        sa.Column("comment", string, nullable=True),
    )
    op.create_index("ix_clientapproval_tenant_id", "clientapproval", ["tenant_id"])
    op.create_index("ix_clientapproval_approval_id", "clientapproval", ["approval_id"], unique=True)
    op.create_index("ix_clientapproval_request_id", "clientapproval", ["request_id"])
    op.create_index("ix_clientapproval_export_id", "clientapproval", ["export_id"])

    op.create_table(
        "purchaseauthorization",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", string, nullable=False),
        sa.Column("authorization_id", string, nullable=False),
        sa.Column("request_id", string, nullable=False),
        sa.Column("approval_id", string, nullable=False),
        sa.Column("authorized_by", string, nullable=False),
        sa.Column("authorized_at", sa.DateTime(), nullable=False),
        sa.Column("status", string, nullable=False),
        sa.Column("comment", string, nullable=True),
    )
    op.create_index("ix_purchaseauthorization_tenant_id", "purchaseauthorization", ["tenant_id"])
    op.create_index("ix_purchaseauthorization_authorization_id", "purchaseauthorization", ["authorization_id"], unique=True)
    op.create_index("ix_purchaseauthorization_request_id", "purchaseauthorization", ["request_id"])
    op.create_index("ix_purchaseauthorization_approval_id", "purchaseauthorization", ["approval_id"])

def downgrade() -> None:
    op.drop_table("purchaseauthorization")
    op.drop_table("clientapproval")
    op.drop_table("contractexceptionrecord")
    op.drop_table("adaptationdecisionrecord")
    op.drop_table("contractgap")
    op.drop_table("requirementcoverage")
    op.drop_table("contractrequirement")
    op.drop_table("contractauditrun")

    with op.batch_alter_table("contractexport") as batch:
        for column in ("diff_status", "registry_hash", "document_version"):
            if column in _columns("contractexport"):
                batch.drop_column(column)

    with op.batch_alter_table("priceevidence") as batch:
        for column in (
            "evidence_status", "comparability_status", "unavailable_reason", "retry_count",
            "parser_version", "html_sha256", "order_status", "delivery_eta_days", "delivery_region",
            "warehouse", "available_quantity", "vat_included", "condition", "unit",
            "package_quantity", "availability_status", "expires_at", "freshness_ttl_hours",
        ):
            if column in _columns("priceevidence"):
                batch.drop_column(column)

    with op.batch_alter_table("contractposition") as batch:
        for column in (
            "calculation_json", "selected_reason", "change_reason", "blocking_error_code",
            "blocking_status", "completeness_status", "requirement_id", "warranty_impact",
            "safety_related", "max_delivery_days", "delivery_deadline_at", "criticality",
            "vin_checked_at", "vehicle_data_source", "vehicle_identity_status",
            "position_version", "position_uuid",
        ):
            if column in _columns("contractposition"):
                batch.drop_column(column)
