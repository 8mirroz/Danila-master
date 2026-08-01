"""add scoped service api keys

Revision ID: 5e9a2c3d6f40
Revises: 4d8f1a2b5c30
"""
from alembic import op
import sqlalchemy as sa

revision = "5e9a2c3d6f40"
down_revision = "4d8f1a2b5c30"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("serviceapikey", sa.Column("id", sa.Integer(), nullable=False), sa.Column("key_id", sa.String(), nullable=False), sa.Column("organization_id", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("key_hash", sa.String(), nullable=False), sa.Column("scopes_json", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.Column("last_used_at", sa.DateTime(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("revoked_at", sa.DateTime(), nullable=True), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("key_id", name="uq_service_api_key_id"))
    op.create_index("ix_serviceapikey_key_id", "serviceapikey", ["key_id"], unique=True)
    op.create_index("ix_serviceapikey_organization_id", "serviceapikey", ["organization_id"])
    op.create_index("ix_serviceapikey_status", "serviceapikey", ["status"])

def downgrade():
    op.drop_index("ix_serviceapikey_status", table_name="serviceapikey", if_exists=True)
    op.drop_index("ix_serviceapikey_organization_id", table_name="serviceapikey", if_exists=True)
    op.drop_index("ix_serviceapikey_key_id", table_name="serviceapikey", if_exists=True)
    op.drop_table("serviceapikey")
