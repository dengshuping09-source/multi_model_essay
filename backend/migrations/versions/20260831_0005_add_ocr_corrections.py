"""add OCR correction records

Revision ID: 20260831_0005
Revises: 20260815_0004
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0005"
down_revision: str | None = "20260815_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_corrections",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "confirmed",
                name="ocr_correction_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("corrected_text", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["essay_id"], ["essays.id"], name=op.f("fk_ocr_corrections_essay_id_essays"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"], ["ocr_runs.id"], name=op.f("fk_ocr_corrections_ocr_run_id_ocr_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocr_corrections")),
        sa.UniqueConstraint("ocr_run_id", name="ocr_run_correction"),
    )
    op.create_index(op.f("ix_ocr_corrections_essay_id"), "ocr_corrections", ["essay_id"])
    op.create_index(op.f("ix_ocr_corrections_ocr_run_id"), "ocr_corrections", ["ocr_run_id"])

    op.create_table(
        "ocr_block_corrections",
        sa.Column("correction_id", sa.Uuid(), nullable=False),
        sa.Column("ocr_block_id", sa.Uuid(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["correction_id"], ["ocr_corrections.id"], name=op.f("fk_ocr_block_corrections_correction_id_ocr_corrections"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ocr_block_id"], ["ocr_blocks.id"], name=op.f("fk_ocr_block_corrections_ocr_block_id_ocr_blocks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocr_block_corrections")),
        sa.UniqueConstraint("correction_id", "ocr_block_id", name="correction_block"),
    )
    op.create_index(op.f("ix_ocr_block_corrections_correction_id"), "ocr_block_corrections", ["correction_id"])
    op.create_index(op.f("ix_ocr_block_corrections_ocr_block_id"), "ocr_block_corrections", ["ocr_block_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ocr_block_corrections_ocr_block_id"), table_name="ocr_block_corrections")
    op.drop_index(op.f("ix_ocr_block_corrections_correction_id"), table_name="ocr_block_corrections")
    op.drop_table("ocr_block_corrections")
    op.drop_index(op.f("ix_ocr_corrections_ocr_run_id"), table_name="ocr_corrections")
    op.drop_index(op.f("ix_ocr_corrections_essay_id"), table_name="ocr_corrections")
    op.drop_table("ocr_corrections")
