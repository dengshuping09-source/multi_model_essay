"""add upload file metadata

Revision ID: 20260814_0002
Revises: 20260814_0001
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0002"
down_revision: str | None = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("essay_sources", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("essay_sources", sa.Column("image_width", sa.Integer(), nullable=True))
    op.add_column("essay_sources", sa.Column("image_height", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_essay_sources_file_size_positive"),
        "essay_sources",
        "file_size_bytes IS NULL OR file_size_bytes > 0",
    )
    op.create_check_constraint(
        op.f("ck_essay_sources_image_width_positive"),
        "essay_sources",
        "image_width IS NULL OR image_width > 0",
    )
    op.create_check_constraint(
        op.f("ck_essay_sources_image_height_positive"),
        "essay_sources",
        "image_height IS NULL OR image_height > 0",
    )
    op.create_unique_constraint("storage_key_unique", "essay_sources", ["storage_key"])


def downgrade() -> None:
    op.drop_constraint("storage_key_unique", "essay_sources", type_="unique")
    op.drop_constraint(
        op.f("ck_essay_sources_image_height_positive"), "essay_sources", type_="check"
    )
    op.drop_constraint(
        op.f("ck_essay_sources_image_width_positive"), "essay_sources", type_="check"
    )
    op.drop_constraint(
        op.f("ck_essay_sources_file_size_positive"), "essay_sources", type_="check"
    )
    op.drop_column("essay_sources", "image_height")
    op.drop_column("essay_sources", "image_width")
    op.drop_column("essay_sources", "file_size_bytes")

