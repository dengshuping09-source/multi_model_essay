"""add material recent views

Revision ID: 20260914_0016
Revises: 20260914_0015
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260914_0016"
down_revision: str | None = "20260914_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_recent_views",
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.String(length=80), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("author_id", "material_id", name="material_recent_view_unique"),
    )
    op.create_index("ix_material_recent_views_author_id", "material_recent_views", ["author_id"])
    op.create_index("ix_material_recent_views_material_id", "material_recent_views", ["material_id"])
    op.create_index("ix_material_recent_views_last_viewed_at", "material_recent_views", ["last_viewed_at"])


def downgrade() -> None:
    op.drop_index("ix_material_recent_views_last_viewed_at", table_name="material_recent_views")
    op.drop_index("ix_material_recent_views_material_id", table_name="material_recent_views")
    op.drop_index("ix_material_recent_views_author_id", table_name="material_recent_views")
    op.drop_table("material_recent_views")
