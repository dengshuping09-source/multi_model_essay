"""add recheck result links

Revision ID: 20260831_0009
Revises: 20260831_0008
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260831_0009"
down_revision: str | None = "20260831_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_rechecks", sa.Column("recheck_batch_id", sa.Uuid(), nullable=True))
    op.add_column(
        "review_rechecks", sa.Column("resolved_final_evaluation_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_review_rechecks_recheck_batch_id_review_batches"),
        "review_rechecks",
        "review_batches",
        ["recheck_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_review_rechecks_resolved_final_evaluation_id_final_evaluations"),
        "review_rechecks",
        "final_evaluations",
        ["resolved_final_evaluation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_review_rechecks_recheck_batch_id"), "review_rechecks", ["recheck_batch_id"]
    )
    op.create_index(
        op.f("ix_review_rechecks_resolved_final_evaluation_id"),
        "review_rechecks",
        ["resolved_final_evaluation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_review_rechecks_resolved_final_evaluation_id"), table_name="review_rechecks"
    )
    op.drop_index(op.f("ix_review_rechecks_recheck_batch_id"), table_name="review_rechecks")
    op.drop_constraint(
        op.f("fk_review_rechecks_resolved_final_evaluation_id_final_evaluations"),
        "review_rechecks",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_review_rechecks_recheck_batch_id_review_batches"),
        "review_rechecks",
        type_="foreignkey",
    )
    op.drop_column("review_rechecks", "resolved_final_evaluation_id")
    op.drop_column("review_rechecks", "recheck_batch_id")
