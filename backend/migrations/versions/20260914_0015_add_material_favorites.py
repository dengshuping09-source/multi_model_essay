"""add material favorites

Revision ID: 20260914_0015
Revises: 20260913_0014
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260914_0015"
down_revision: str | None = "20260913_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_favorites",
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("author_id", "material_id", name="material_favorite_unique"),
    )
    op.create_index("ix_material_favorites_author_id", "material_favorites", ["author_id"])
    op.create_index("ix_material_favorites_material_id", "material_favorites", ["material_id"])


def downgrade() -> None:
    op.drop_index("ix_material_favorites_material_id", table_name="material_favorites")
    op.drop_index("ix_material_favorites_author_id", table_name="material_favorites")
    op.drop_table("material_favorites")
