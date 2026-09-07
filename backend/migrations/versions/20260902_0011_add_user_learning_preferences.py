"""add user learning preferences

Revision ID: 20260902_0011
Revises: 20260901_0010
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260902_0011"
down_revision: str | None = "20260901_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("grade_level", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("default_genre", sa.String(length=50), nullable=True))
    op.add_column(
        "ai_annotations",
        sa.Column("kind", sa.String(length=20), server_default="improvement", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("ai_annotations", "kind")
    op.drop_column("users", "default_genre")
    op.drop_column("users", "grade_level")
