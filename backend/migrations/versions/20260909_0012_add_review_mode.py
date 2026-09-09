"""add review mode to review batches

Revision ID: 20260909_0012
Revises: 20260902_0011
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260909_0012"
down_revision: str | None = "20260902_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_batches",
        sa.Column("review_mode", sa.String(length=20), server_default="quick", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("review_batches", "review_mode")
