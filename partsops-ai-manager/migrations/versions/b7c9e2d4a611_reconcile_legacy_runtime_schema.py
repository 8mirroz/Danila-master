"""reconcile live legacy schema with current runtime models

This migration is intentionally additive and repairs databases that were
stamped at 50ece6030d5a before the later model fields/indexes were deployed.
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c9e2d4a611"
down_revision = "8a4c2d9e1f70"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # Existing fleet rows created before the model made these values required
    # must be normalized before tightening nullability.
    op.execute("UPDATE fleetvehicle SET odometer_km = 0 WHERE odometer_km IS NULL")
    op.execute("UPDATE fleetvehicle SET fuel_level_percent = 100 WHERE fuel_level_percent IS NULL")
    with op.batch_alter_table("fleetvehicle") as batch:
        batch.alter_column("odometer_km", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("fuel_level_percent", existing_type=sa.Integer(), nullable=False)

    if "ix_fleetvehicle_status" not in _indexes("fleetvehicle"):
        op.create_index("ix_fleetvehicle_status", "fleetvehicle", ["status"], unique=False)

    outbound_columns = _columns("outboundmessage")
    if "max_attempts" not in outbound_columns:
        op.add_column("outboundmessage", sa.Column(
            "max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")))
    if "next_retry_at" not in outbound_columns:
        op.add_column("outboundmessage", sa.Column("next_retry_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    columns = _columns("outboundmessage")
    if "next_retry_at" in columns:
        op.drop_column("outboundmessage", "next_retry_at")
    if "max_attempts" in columns:
        op.drop_column("outboundmessage", "max_attempts")

    if "ix_fleetvehicle_status" in _indexes("fleetvehicle"):
        op.drop_index("ix_fleetvehicle_status", table_name="fleetvehicle")
    with op.batch_alter_table("fleetvehicle") as batch:
        batch.alter_column("odometer_km", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("fuel_level_percent", existing_type=sa.Integer(), nullable=True)
