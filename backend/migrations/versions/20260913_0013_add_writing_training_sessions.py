"""add writing training sessions

Revision ID: 20260913_0013
Revises: 20260909_0012
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260913_0013"
down_revision: str | None = "20260909_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "writing_training_sessions",
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("training_type", sa.String(length=40), server_default="topic_and_idea", nullable=False),
        sa.Column("topic_prompt", sa.Text(), nullable=False),
        sa.Column("requirement_notes", sa.Text(), nullable=False),
        sa.Column("central_idea", sa.Text(), nullable=False),
        sa.Column("outline", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="running", nullable=False),
        sa.Column("feedback", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_key", sa.String(length=40), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_writing_training_sessions_author_id",
        "writing_training_sessions",
        ["author_id"],
    )
    op.create_index(
        "ix_writing_training_sessions_status",
        "writing_training_sessions",
        ["status"],
    )
    op.create_index(
        "ix_writing_training_sessions_training_type",
        "writing_training_sessions",
        ["training_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_writing_training_sessions_training_type", table_name="writing_training_sessions")
    op.drop_index("ix_writing_training_sessions_status", table_name="writing_training_sessions")
    op.drop_index("ix_writing_training_sessions_author_id", table_name="writing_training_sessions")
    op.drop_table("writing_training_sessions")
