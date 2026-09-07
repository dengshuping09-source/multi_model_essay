"""add accounts, essay context, and multi-model review workflow

Revision ID: 20260831_0008
Revises: 20260831_0007
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260831_0008"
down_revision: str | None = "20260831_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def review_status_enum(name: str) -> sa.Enum:
    return sa.Enum(
        "pending", "running", "completed", "failed", name=name,
        native_enum=False, create_constraint=True, length=32,
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"])
    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name=op.f("fk_user_sessions_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_sessions_token_hash")),
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"])
    op.create_index(op.f("ix_user_sessions_token_hash"), "user_sessions", ["token_hash"])
    op.create_index(op.f("ix_user_sessions_expires_at"), "user_sessions", ["expires_at"])

    op.add_column("essays", sa.Column("author_id", sa.Uuid(), nullable=True))
    op.add_column("essays", sa.Column("grade_level", sa.String(length=50), nullable=True))
    op.add_column("essays", sa.Column("genre", sa.String(length=50), nullable=True))
    op.add_column("essays", sa.Column("writing_prompt", sa.Text(), nullable=True))
    op.add_column("essays", sa.Column("full_score", sa.Integer(), server_default="100", nullable=False))
    op.create_foreign_key(op.f("fk_essays_author_id_users"), "essays", "users", ["author_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_essays_author_id"), "essays", ["author_id"])
    op.create_check_constraint(op.f("ck_essays_full_score_positive"), "essays", "full_score > 0")

    op.create_table(
        "review_batches",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("requested_providers", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("scoring_standard_version", sa.String(length=100), nullable=False),
        sa.Column("status", review_status_enum("review_batch_status"), nullable=False),
        sa.Column("text_source", sa.String(length=40), nullable=False),
        sa.Column("evaluated_text", sa.Text(), nullable=False),
        sa.Column("retry_of_batch_id", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"], ondelete="CASCADE", name=op.f("fk_review_batches_essay_id_essays")),
        sa.ForeignKeyConstraint(["retry_of_batch_id"], ["review_batches.id"], ondelete="SET NULL", name=op.f("fk_review_batches_retry_of_batch_id_review_batches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_batches")),
    )
    op.create_index(op.f("ix_review_batches_essay_id"), "review_batches", ["essay_id"])

    op.add_column("model_reviews", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.add_column("model_reviews", sa.Column("scoring_standard_version", sa.String(length=100), nullable=True))
    op.add_column("model_reviews", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
    op.create_foreign_key(op.f("fk_model_reviews_batch_id_review_batches"), "model_reviews", "review_batches", ["batch_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_model_reviews_batch_id"), "model_reviews", ["batch_id"])
    op.add_column("ai_annotations", sa.Column("ocr_block_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f("fk_ai_annotations_ocr_block_id_ocr_blocks"), "ai_annotations", "ocr_blocks", ["ocr_block_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_ai_annotations_ocr_block_id"), "ai_annotations", ["ocr_block_id"])

    op.add_column("final_evaluations", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.add_column("final_evaluations", sa.Column("scoring_standard_version", sa.String(length=100), nullable=True))
    op.add_column("final_evaluations", sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True))
    op.add_column("final_evaluations", sa.Column("consistency", sa.String(length=30), nullable=True))
    op.add_column("final_evaluations", sa.Column("disputes", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("final_evaluations", sa.Column("aggregation_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key(op.f("fk_final_evaluations_batch_id_review_batches"), "final_evaluations", "review_batches", ["batch_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_final_evaluations_batch_id"), "final_evaluations", ["batch_id"])

    op.create_table(
        "review_rechecks",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("final_evaluation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum("pending", "running", "completed", "skipped", "failed", name="review_recheck_status", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column("requested_providers", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["batch_id"], ["review_batches.id"], ondelete="CASCADE", name=op.f("fk_review_rechecks_batch_id_review_batches")),
        sa.ForeignKeyConstraint(["final_evaluation_id"], ["final_evaluations.id"], ondelete="SET NULL", name=op.f("fk_review_rechecks_final_evaluation_id_final_evaluations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_rechecks")),
    )
    op.create_index(op.f("ix_review_rechecks_batch_id"), "review_rechecks", ["batch_id"])
    op.create_index(op.f("ix_review_rechecks_final_evaluation_id"), "review_rechecks", ["final_evaluation_id"])
    op.create_table(
        "reference_assessments",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("overall_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("dimension_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), server_default="teacher", nullable=False),
        sa.Column("is_final", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"], ondelete="CASCADE", name=op.f("fk_reference_assessments_essay_id_essays")),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL", name=op.f("fk_reference_assessments_recorded_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_assessments")),
    )
    op.create_index(op.f("ix_reference_assessments_essay_id"), "reference_assessments", ["essay_id"])
    op.create_index(op.f("ix_reference_assessments_recorded_by_user_id"), "reference_assessments", ["recorded_by_user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_reference_assessments_recorded_by_user_id"), table_name="reference_assessments")
    op.drop_index(op.f("ix_reference_assessments_essay_id"), table_name="reference_assessments")
    op.drop_table("reference_assessments")
    op.drop_index(op.f("ix_review_rechecks_final_evaluation_id"), table_name="review_rechecks")
    op.drop_index(op.f("ix_review_rechecks_batch_id"), table_name="review_rechecks")
    op.drop_table("review_rechecks")
    op.drop_index(op.f("ix_final_evaluations_batch_id"), table_name="final_evaluations")
    op.drop_constraint(op.f("fk_final_evaluations_batch_id_review_batches"), "final_evaluations", type_="foreignkey")
    for column in ["aggregation_config", "disputes", "consistency", "confidence", "scoring_standard_version", "batch_id"]:
        op.drop_column("final_evaluations", column)
    op.drop_index(op.f("ix_ai_annotations_ocr_block_id"), table_name="ai_annotations")
    op.drop_constraint(op.f("fk_ai_annotations_ocr_block_id_ocr_blocks"), "ai_annotations", type_="foreignkey")
    op.drop_column("ai_annotations", "ocr_block_id")
    op.drop_index(op.f("ix_model_reviews_batch_id"), table_name="model_reviews")
    op.drop_constraint(op.f("fk_model_reviews_batch_id_review_batches"), "model_reviews", type_="foreignkey")
    for column in ["retry_count", "scoring_standard_version", "batch_id"]:
        op.drop_column("model_reviews", column)
    op.drop_index(op.f("ix_review_batches_essay_id"), table_name="review_batches")
    op.drop_table("review_batches")
    op.drop_constraint(op.f("ck_essays_full_score_positive"), "essays", type_="check")
    op.drop_index(op.f("ix_essays_author_id"), table_name="essays")
    op.drop_constraint(op.f("fk_essays_author_id_users"), "essays", type_="foreignkey")
    for column in ["full_score", "writing_prompt", "genre", "grade_level", "author_id"]:
        op.drop_column("essays", column)
    op.drop_index(op.f("ix_user_sessions_expires_at"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_token_hash"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
