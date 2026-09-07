"""add review text traceability

Revision ID: 20260831_0006
Revises: 20260831_0005
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260831_0006"
down_revision: str | None = "20260831_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_reviews",
        sa.Column("text_source", sa.String(length=40), server_default="direct_input", nullable=False),
    )
    op.add_column(
        "model_reviews",
        sa.Column("evaluated_text", sa.Text(), server_default="", nullable=False),
    )
    op.add_column("ai_annotations", sa.Column("evidence_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_annotations", "evidence_text")
    op.drop_column("model_reviews", "evaluated_text")
    op.drop_column("model_reviews", "text_source")
