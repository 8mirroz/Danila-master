"""add email_messages.duplicate_hits denormalized redelivery counter

Revision ID: c8e1a2b3d4f0
Revises: b1c2d3e4f5a6
Create Date: 2026-08-12

"""
from alembic import op
import sqlalchemy as sa
import json

revision = "c8e1a2b3d4f0"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "email_messages",
        sa.Column("duplicate_hits", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_email_messages_duplicate_hits",
        "email_messages",
        ["duplicate_hits"],
        unique=False,
    )
    # Best-effort backfill from auth_results_json.duplicate_hits (sqlite/pg).
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, auth_results_json FROM email_messages")).fetchall()
    for row in rows:
        mid, ar_json = row[0], row[1]
        hits = 0
        try:
            data = json.loads(ar_json or "{}")
            if isinstance(data, dict):
                hits = int(data.get("duplicate_hits") or 0)
        except Exception:
            hits = 0
        if hits > 0:
            conn.execute(
                sa.text("UPDATE email_messages SET duplicate_hits = :h WHERE id = :id"),
                {"h": hits, "id": mid},
            )


def downgrade():
    op.drop_index("ix_email_messages_duplicate_hits", table_name="email_messages")
    op.drop_column("email_messages", "duplicate_hits")
