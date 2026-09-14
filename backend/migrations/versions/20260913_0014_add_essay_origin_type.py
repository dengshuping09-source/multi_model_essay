"""add essay origin type

Revision ID: 20260913_0014
Revises: 20260913_0013
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260913_0014"
down_revision: str | None = "20260913_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "essays",
        sa.Column("origin_type", sa.String(length=30), server_default="standard", nullable=False),
    )
    op.create_index("ix_essays_origin_type", "essays", ["origin_type"])


def downgrade() -> None:
    op.drop_index("ix_essays_origin_type", table_name="essays")
    op.drop_column("essays", "origin_type")
