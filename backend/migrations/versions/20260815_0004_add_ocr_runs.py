"""add OCR runs and page results

Revision ID: 20260815_0004
Revises: 20260814_0003
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0004"
down_revision: str | None = "20260814_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "image_quality_analyses",
        sa.Column(
            "original_to_processed_matrix",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "image_quality_analyses",
        sa.Column(
            "processed_to_original_matrix",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.create_table(
        "ocr_runs",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "completed",
                "partial",
                "failed",
                name="ocr_run_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("engine_name", sa.String(length=80), nullable=False),
        sa.Column("detection_model", sa.String(length=100), nullable=False),
        sa.Column("recognition_model", sa.String(length=100), nullable=False),
        sa.Column("combined_text", sa.Text(), nullable=True),
        sa.Column("average_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("total_blocks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("attempt_no >= 1", name=op.f("ck_ocr_runs_attempt_positive")),
        sa.CheckConstraint(
            "average_confidence IS NULL OR (average_confidence >= 0 AND average_confidence <= 1)",
            name=op.f("ck_ocr_runs_average_confidence_range"),
        ),
        sa.CheckConstraint("total_blocks >= 0", name=op.f("ck_ocr_runs_total_blocks_non_negative")),
        sa.ForeignKeyConstraint(
            ["essay_id"],
            ["essays.id"],
            name=op.f("fk_ocr_runs_essay_id_essays"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocr_runs")),
        sa.UniqueConstraint("essay_id", "attempt_no", name="essay_ocr_attempt"),
    )
    op.create_index(op.f("ix_ocr_runs_essay_id"), "ocr_runs", ["essay_id"])

    op.create_table(
        "ocr_page_results",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "completed",
                "low_confidence",
                "empty",
                "skipped_quality",
                "failed",
                name="ocr_page_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "input_variant",
            sa.Enum(
                "original",
                "processed",
                name="ocr_input_variant",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("input_storage_key", sa.String(length=500), nullable=False),
        sa.Column("input_width", sa.Integer(), nullable=False),
        sa.Column("input_height", sa.Integer(), nullable=False),
        sa.Column("input_to_original_matrix", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("combined_text", sa.Text(), nullable=True),
        sa.Column("average_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("block_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "average_confidence IS NULL OR (average_confidence >= 0 AND average_confidence <= 1)",
            name=op.f("ck_ocr_page_results_average_confidence_range"),
        ),
        sa.CheckConstraint("block_count >= 0", name=op.f("ck_ocr_page_results_block_count_non_negative")),
        sa.CheckConstraint("input_height > 0", name=op.f("ck_ocr_page_results_input_height_positive")),
        sa.CheckConstraint("input_width > 0", name=op.f("ck_ocr_page_results_input_width_positive")),
        sa.CheckConstraint("page_number >= 1", name=op.f("ck_ocr_page_results_page_positive")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["ocr_runs.id"],
            name=op.f("fk_ocr_page_results_run_id_ocr_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["essay_sources.id"],
            name=op.f("fk_ocr_page_results_source_id_essay_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocr_page_results")),
        sa.UniqueConstraint("run_id", "page_number", name="ocr_run_page"),
        sa.UniqueConstraint("run_id", "source_id", name="ocr_run_source"),
    )
    op.create_index(op.f("ix_ocr_page_results_run_id"), "ocr_page_results", ["run_id"])
    op.create_index(op.f("ix_ocr_page_results_source_id"), "ocr_page_results", ["source_id"])

    op.drop_constraint("source_block_index", "ocr_blocks", type_="unique")
    op.add_column("ocr_blocks", sa.Column("page_result_id", sa.Uuid(), nullable=True))
    op.add_column(
        "ocr_blocks",
        sa.Column("polygon_original", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_ocr_blocks_page_result_id_ocr_page_results"),
        "ocr_blocks",
        "ocr_page_results",
        ["page_result_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_ocr_blocks_page_result_id"), "ocr_blocks", ["page_result_id"])
    op.create_unique_constraint(
        "page_result_block_index", "ocr_blocks", ["page_result_id", "block_index"]
    )


def downgrade() -> None:
    op.drop_constraint("page_result_block_index", "ocr_blocks", type_="unique")
    op.drop_index(op.f("ix_ocr_blocks_page_result_id"), table_name="ocr_blocks")
    op.drop_constraint(
        op.f("fk_ocr_blocks_page_result_id_ocr_page_results"),
        "ocr_blocks",
        type_="foreignkey",
    )
    op.drop_column("ocr_blocks", "polygon_original")
    op.drop_column("ocr_blocks", "page_result_id")
    op.create_unique_constraint("source_block_index", "ocr_blocks", ["source_id", "block_index"])

    op.drop_index(op.f("ix_ocr_page_results_source_id"), table_name="ocr_page_results")
    op.drop_index(op.f("ix_ocr_page_results_run_id"), table_name="ocr_page_results")
    op.drop_table("ocr_page_results")
    op.drop_index(op.f("ix_ocr_runs_essay_id"), table_name="ocr_runs")
    op.drop_table("ocr_runs")
    op.drop_column("image_quality_analyses", "processed_to_original_matrix")
    op.drop_column("image_quality_analyses", "original_to_processed_matrix")
