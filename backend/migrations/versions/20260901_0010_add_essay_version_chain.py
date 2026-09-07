"""add persistent essay version chain

Revision ID: 20260901_0010
Revises: 20260831_0009
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260901_0010"
down_revision: str | None = "20260831_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("essays", sa.Column("root_essay_id", sa.Uuid(), nullable=True))
    op.add_column("essays", sa.Column("parent_essay_id", sa.Uuid(), nullable=True))
    op.add_column(
        "essays", sa.Column("version_no", sa.Integer(), server_default="1", nullable=False)
    )
    op.execute("UPDATE essays SET root_essay_id = id WHERE root_essay_id IS NULL")
    op.alter_column("essays", "root_essay_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_essays_root_essay_id_essays"),
        "essays",
        "essays",
        ["root_essay_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_essays_parent_essay_id_essays"),
        "essays",
        "essays",
        ["parent_essay_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_essays_root_essay_id"), "essays", ["root_essay_id"])
    op.create_index(op.f("ix_essays_parent_essay_id"), "essays", ["parent_essay_id"])
    op.create_unique_constraint("essay_root_version", "essays", ["root_essay_id", "version_no"])
    op.create_check_constraint("essay_version_positive", "essays", "version_no >= 1")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_essays_essay_version_positive"), "essays", type_="check")
    op.drop_constraint("essay_root_version", "essays", type_="unique")
    op.drop_index(op.f("ix_essays_parent_essay_id"), table_name="essays")
    op.drop_index(op.f("ix_essays_root_essay_id"), table_name="essays")
    op.drop_constraint(
        op.f("fk_essays_parent_essay_id_essays"), "essays", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_essays_root_essay_id_essays"), "essays", type_="foreignkey"
    )
    op.drop_column("essays", "version_no")
    op.drop_column("essays", "parent_essay_id")
    op.drop_column("essays", "root_essay_id")
