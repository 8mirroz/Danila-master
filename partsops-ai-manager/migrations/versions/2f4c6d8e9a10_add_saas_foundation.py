"""add SaaS foundation tables

Revision ID: 2f4c6d8e9a10
Revises: 9c5d7e1a2b34
"""
from alembic import op
import sqlalchemy as sa

revision = "2f4c6d8e9a10"
down_revision = "9c5d7e1a2b34"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("tax_policy", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_organization_organization_id", "organization", ["organization_id"], unique=True)
    op.create_index("ix_organization_status", "organization", ["status"], unique=False)

    op.create_table(
        "appuser",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("external_subject", sa.String(), nullable=True),
        sa.Column("identity_provider", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_appuser_email", "appuser", ["email"], unique=False)
    op.create_index("ix_appuser_external_subject", "appuser", ["external_subject"], unique=False)
    op.create_index("ix_appuser_status", "appuser", ["status"], unique=False)
    op.create_index("ix_appuser_user_id", "appuser", ["user_id"], unique=True)

    op.create_table(
        "membership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("invited_by", sa.String(), nullable=True),
        sa.Column("invited_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_index("ix_membership_organization_id", "membership", ["organization_id"], unique=False)
    op.create_index("ix_membership_status", "membership", ["status"], unique=False)
    op.create_index("ix_membership_user_id", "membership", ["user_id"], unique=False)

    op.create_table(
        "subscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("plan_code", sa.String(), nullable=False),
        sa.Column("position_limit", sa.Integer(), nullable=False),
        sa.Column("supplier_feed_limit", sa.Integer(), nullable=False),
        sa.Column("user_limit", sa.Integer(), nullable=False),
        sa.Column("external_invoice_number", sa.String(), nullable=True),
        sa.Column("external_invoice_date", sa.String(), nullable=True),
        sa.Column("trial_started_at", sa.DateTime(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_subscription_organization_id", "subscription", ["organization_id"], unique=True)
    op.create_index("ix_subscription_plan_code", "subscription", ["plan_code"], unique=False)
    op.create_index("ix_subscription_status", "subscription", ["status"], unique=False)

    op.create_table(
        "usageevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("metadata_json", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_usageevent_event_type", "usageevent", ["event_type"], unique=False)
    op.create_index("ix_usageevent_idempotency_key", "usageevent", ["idempotency_key"], unique=True)
    op.create_index("ix_usageevent_organization_id", "usageevent", ["organization_id"], unique=False)
    op.create_index("ix_usageevent_request_id", "usageevent", ["request_id"], unique=False)

    op.create_table(
        "integrationconnection",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scopes_json", sa.String(), nullable=True),
        sa.Column("config_ref", sa.String(), nullable=True),
        sa.Column("last_health_status", sa.String(), nullable=True),
        sa.Column("last_health_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", "name", name="uq_integration_org_provider_name"),
    )
    op.create_index("ix_integrationconnection_organization_id", "integrationconnection", ["organization_id"], unique=False)
    op.create_index("ix_integrationconnection_provider", "integrationconnection", ["provider"], unique=False)
    op.create_index("ix_integrationconnection_status", "integrationconnection", ["status"], unique=False)

    op.create_table(
        "onboardingstate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("checklist_json", sa.String(), nullable=True),
        sa.Column("completed_steps_json", sa.String(), nullable=True),
        sa.Column("first_catalog_imported_at", sa.DateTime(), nullable=True),
        sa.Column("first_rfq_processed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_onboardingstate_organization_id", "onboardingstate", ["organization_id"], unique=True)
    op.create_index("ix_onboardingstate_status", "onboardingstate", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_onboardingstate_status", table_name="onboardingstate", if_exists=True)
    op.drop_index("ix_onboardingstate_organization_id", table_name="onboardingstate", if_exists=True)
    op.drop_table("onboardingstate")
    op.drop_index("ix_integrationconnection_status", table_name="integrationconnection", if_exists=True)
    op.drop_index("ix_integrationconnection_provider", table_name="integrationconnection", if_exists=True)
    op.drop_index("ix_integrationconnection_organization_id", table_name="integrationconnection", if_exists=True)
    op.drop_table("integrationconnection")
    op.drop_index("ix_usageevent_request_id", table_name="usageevent", if_exists=True)
    op.drop_index("ix_usageevent_organization_id", table_name="usageevent", if_exists=True)
    op.drop_index("ix_usageevent_idempotency_key", table_name="usageevent", if_exists=True)
    op.drop_index("ix_usageevent_event_type", table_name="usageevent", if_exists=True)
    op.drop_table("usageevent")
    op.drop_index("ix_subscription_status", table_name="subscription", if_exists=True)
    op.drop_index("ix_subscription_plan_code", table_name="subscription", if_exists=True)
    op.drop_index("ix_subscription_organization_id", table_name="subscription", if_exists=True)
    op.drop_table("subscription")
    op.drop_index("ix_membership_user_id", table_name="membership", if_exists=True)
    op.drop_index("ix_membership_status", table_name="membership", if_exists=True)
    op.drop_index("ix_membership_organization_id", table_name="membership", if_exists=True)
    op.drop_table("membership")
    op.drop_index("ix_appuser_user_id", table_name="appuser", if_exists=True)
    op.drop_index("ix_appuser_status", table_name="appuser", if_exists=True)
    op.drop_index("ix_appuser_external_subject", table_name="appuser", if_exists=True)
    op.drop_index("ix_appuser_email", table_name="appuser", if_exists=True)
    op.drop_table("appuser")
    op.drop_index("ix_organization_status", table_name="organization", if_exists=True)
    op.drop_index("ix_organization_organization_id", table_name="organization", if_exists=True)
    op.drop_table("organization")
