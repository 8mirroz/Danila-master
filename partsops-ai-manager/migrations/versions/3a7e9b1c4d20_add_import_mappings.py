"""add reusable import mappings

Revision ID: 3a7e9b1c4d20
Revises: 2f4c6d8e9a10
"""
from alembic import op
import sqlalchemy as sa
revision = "3a7e9b1c4d20"
down_revision = "2f4c6d8e9a10"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("importmapping", sa.Column("id", sa.Integer(), nullable=False), sa.Column("organization_id", sa.String(), nullable=False), sa.Column("kind", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("mapping_json", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("organization_id", "kind", "name", name="uq_import_mapping_org_kind_name"))
    op.create_index("ix_importmapping_organization_id", "importmapping", ["organization_id"])
    op.create_index("ix_importmapping_kind", "importmapping", ["kind"])
def downgrade():
    op.drop_index("ix_importmapping_kind", table_name="importmapping", if_exists=True)
    op.drop_index("ix_importmapping_organization_id", table_name="importmapping", if_exists=True)
    op.drop_table("importmapping")
