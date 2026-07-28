"""reconcile analog candidate columns with the runtime model

The original compatibility migration created the legacy risk columns, while
the current AnalogCandidate model uses the normalized quality/risk fields.
Keep the legacy columns for backward compatibility and add the runtime fields
additively so contract-control reads work on existing databases.
"""

from alembic import op
import sqlalchemy as sa


revision = "8b2c4d6e7f90"
down_revision = "7a1b2c3d4e5f"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _columns("analogcandidate")
    with op.batch_alter_table("analogcandidate") as batch:
        if "quality_tier" not in existing:
            batch.add_column(sa.Column(
                "quality_tier", sa.String(), nullable=False,
                server_default="PREMIUM_AFTERMARKET",
            ))
        if "risk_score" not in existing:
            batch.add_column(sa.Column(
                "risk_score", sa.Integer(), nullable=False,
                server_default="15",
            ))
        if "risk_factors_json" not in existing:
            batch.add_column(sa.Column("risk_factors_json", sa.String(), nullable=True))
        if "price_delta_percent" not in existing:
            batch.add_column(sa.Column("price_delta_percent", sa.Float(), nullable=True))
        if "eta_delta_days" not in existing:
            batch.add_column(sa.Column("eta_delta_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    existing = _columns("analogcandidate")
    with op.batch_alter_table("analogcandidate") as batch:
        for column in (
            "eta_delta_days",
            "price_delta_percent",
            "risk_factors_json",
            "risk_score",
            "quality_tier",
        ):
            if column in existing:
                batch.drop_column(column)
