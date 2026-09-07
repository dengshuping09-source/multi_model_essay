"""create core essay evaluation schema

Revision ID: 20260814_0001
Revises:
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "essays",
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "ready",
                "evaluated",
                name="essay_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_essays")),
    )
    op.create_table(
        "essay_sources",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "text_input",
                "image_upload",
                "document_upload",
                name="source_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("sequence_no", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("page_number IS NULL OR page_number >= 1", name=op.f("ck_essay_sources_page_positive")),
        sa.CheckConstraint("sequence_no >= 0", name=op.f("ck_essay_sources_sequence_non_negative")),
        sa.ForeignKeyConstraint(
            ["essay_id"], ["essays.id"], name=op.f("fk_essay_sources_essay_id_essays"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_essay_sources")),
        sa.UniqueConstraint("essay_id", "sequence_no", name="source_sequence"),
    )
    op.create_index(op.f("ix_essay_sources_essay_id"), "essay_sources", ["essay_id"])

    op.create_table(
        "essay_sentences",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("char_end > char_start", name=op.f("ck_essay_sentences_char_range_valid")),
        sa.CheckConstraint("char_start >= 0", name=op.f("ck_essay_sentences_char_start_non_negative")),
        sa.CheckConstraint("position >= 0", name=op.f("ck_essay_sentences_position_non_negative")),
        sa.ForeignKeyConstraint(
            ["essay_id"], ["essays.id"], name=op.f("fk_essay_sentences_essay_id_essays"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_essay_sentences")),
        sa.UniqueConstraint("essay_id", "position", name="essay_sentence_position"),
    )
    op.create_index(op.f("ix_essay_sentences_essay_id"), "essay_sentences", ["essay_id"])

    op.create_table(
        "model_reviews",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("model_provider", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("attempt_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                name="review_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("overall_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("dimension_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("attempt_no >= 1", name=op.f("ck_model_reviews_attempt_positive")),
        sa.ForeignKeyConstraint(
            ["essay_id"], ["essays.id"], name=op.f("fk_model_reviews_essay_id_essays"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_reviews")),
        sa.UniqueConstraint(
            "essay_id", "model_provider", "model_name", "attempt_no", name="model_attempt"
        ),
    )
    op.create_index(op.f("ix_model_reviews_essay_id"), "model_reviews", ["essay_id"])

    op.create_table(
        "final_evaluations",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                name="final_evaluation_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("overall_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("dimension_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("version >= 1", name=op.f("ck_final_evaluations_version_positive")),
        sa.ForeignKeyConstraint(
            ["essay_id"], ["essays.id"], name=op.f("fk_final_evaluations_essay_id_essays"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_final_evaluations")),
        sa.UniqueConstraint("essay_id", "version", name="essay_final_version"),
    )
    op.create_index(op.f("ix_final_evaluations_essay_id"), "final_evaluations", ["essay_id"])

    op.create_table(
        "ocr_blocks",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("block_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("polygon", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("block_index >= 0", name=op.f("ck_ocr_blocks_block_index_non_negative")),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_ocr_blocks_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["essay_sources.id"], name=op.f("fk_ocr_blocks_source_id_essay_sources"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocr_blocks")),
        sa.UniqueConstraint("source_id", "block_index", name="source_block_index"),
    )
    op.create_index(op.f("ix_ocr_blocks_source_id"), "ocr_blocks", ["source_id"])

    op.create_table(
        "ai_annotations",
        sa.Column("model_review_id", sa.Uuid(), nullable=False),
        sa.Column("sentence_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("end_offset IS NULL OR end_offset > start_offset", name=op.f("ck_ai_annotations_offset_range_valid")),
        sa.CheckConstraint("start_offset IS NULL OR start_offset >= 0", name=op.f("ck_ai_annotations_start_non_negative")),
        sa.ForeignKeyConstraint(
            ["model_review_id"], ["model_reviews.id"], name=op.f("fk_ai_annotations_model_review_id_model_reviews"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sentence_id"], ["essay_sentences.id"], name=op.f("fk_ai_annotations_sentence_id_essay_sentences"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_annotations")),
    )
    op.create_index(op.f("ix_ai_annotations_model_review_id"), "ai_annotations", ["model_review_id"])
    op.create_index(op.f("ix_ai_annotations_sentence_id"), "ai_annotations", ["sentence_id"])

    op.create_table(
        "sentence_ocr_mappings",
        sa.Column("sentence_id", sa.Uuid(), nullable=False),
        sa.Column("ocr_block_id", sa.Uuid(), nullable=False),
        sa.Column("sentence_start", sa.Integer(), nullable=True),
        sa.Column("sentence_end", sa.Integer(), nullable=True),
        sa.Column("ocr_start", sa.Integer(), nullable=True),
        sa.Column("ocr_end", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("ocr_end IS NULL OR ocr_end > ocr_start", name=op.f("ck_sentence_ocr_mappings_ocr_range_valid")),
        sa.CheckConstraint("ocr_start IS NULL OR ocr_start >= 0", name=op.f("ck_sentence_ocr_mappings_ocr_start_non_negative")),
        sa.CheckConstraint("sentence_end IS NULL OR sentence_end > sentence_start", name=op.f("ck_sentence_ocr_mappings_sentence_range_valid")),
        sa.CheckConstraint("sentence_start IS NULL OR sentence_start >= 0", name=op.f("ck_sentence_ocr_mappings_sentence_start_non_negative")),
        sa.ForeignKeyConstraint(
            ["ocr_block_id"], ["ocr_blocks.id"], name=op.f("fk_sentence_ocr_mappings_ocr_block_id_ocr_blocks"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sentence_id"], ["essay_sentences.id"], name=op.f("fk_sentence_ocr_mappings_sentence_id_essay_sentences"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sentence_ocr_mappings")),
    )
    op.create_index(op.f("ix_sentence_ocr_mappings_ocr_block_id"), "sentence_ocr_mappings", ["ocr_block_id"])
    op.create_index(op.f("ix_sentence_ocr_mappings_sentence_id"), "sentence_ocr_mappings", ["sentence_id"])

    op.create_table(
        "score_evidence",
        sa.Column("model_review_id", sa.Uuid(), nullable=False),
        sa.Column("sentence_id", sa.Uuid(), nullable=True),
        sa.Column("annotation_id", sa.Uuid(), nullable=True),
        sa.Column("dimension", sa.String(length=80), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("score_value", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["annotation_id"], ["ai_annotations.id"], name=op.f("fk_score_evidence_annotation_id_ai_annotations"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["model_review_id"], ["model_reviews.id"], name=op.f("fk_score_evidence_model_review_id_model_reviews"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sentence_id"], ["essay_sentences.id"], name=op.f("fk_score_evidence_sentence_id_essay_sentences"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score_evidence")),
    )
    op.create_index(op.f("ix_score_evidence_annotation_id"), "score_evidence", ["annotation_id"])
    op.create_index(op.f("ix_score_evidence_model_review_id"), "score_evidence", ["model_review_id"])
    op.create_index(op.f("ix_score_evidence_sentence_id"), "score_evidence", ["sentence_id"])

    op.create_table(
        "final_evaluation_reviews",
        sa.Column("final_evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("model_review_id", sa.Uuid(), nullable=False),
        sa.Column("weight", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.ForeignKeyConstraint(
            ["final_evaluation_id"], ["final_evaluations.id"], name=op.f("fk_final_evaluation_reviews_final_evaluation_id_final_evaluations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["model_review_id"], ["model_reviews.id"], name=op.f("fk_final_evaluation_reviews_model_review_id_model_reviews"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("final_evaluation_id", "model_review_id", name=op.f("pk_final_evaluation_reviews")),
    )


def downgrade() -> None:
    op.drop_table("final_evaluation_reviews")
    op.drop_index(op.f("ix_score_evidence_sentence_id"), table_name="score_evidence")
    op.drop_index(op.f("ix_score_evidence_model_review_id"), table_name="score_evidence")
    op.drop_index(op.f("ix_score_evidence_annotation_id"), table_name="score_evidence")
    op.drop_table("score_evidence")
    op.drop_index(op.f("ix_sentence_ocr_mappings_sentence_id"), table_name="sentence_ocr_mappings")
    op.drop_index(op.f("ix_sentence_ocr_mappings_ocr_block_id"), table_name="sentence_ocr_mappings")
    op.drop_table("sentence_ocr_mappings")
    op.drop_index(op.f("ix_ai_annotations_sentence_id"), table_name="ai_annotations")
    op.drop_index(op.f("ix_ai_annotations_model_review_id"), table_name="ai_annotations")
    op.drop_table("ai_annotations")
    op.drop_index(op.f("ix_ocr_blocks_source_id"), table_name="ocr_blocks")
    op.drop_table("ocr_blocks")
    op.drop_index(op.f("ix_final_evaluations_essay_id"), table_name="final_evaluations")
    op.drop_table("final_evaluations")
    op.drop_index(op.f("ix_model_reviews_essay_id"), table_name="model_reviews")
    op.drop_table("model_reviews")
    op.drop_index(op.f("ix_essay_sentences_essay_id"), table_name="essay_sentences")
    op.drop_table("essay_sentences")
    op.drop_index(op.f("ix_essay_sources_essay_id"), table_name="essay_sources")
    op.drop_table("essay_sources")
    op.drop_table("essays")

