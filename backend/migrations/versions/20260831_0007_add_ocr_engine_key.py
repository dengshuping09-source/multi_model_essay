"""add OCR engine key

Revision ID: 20260831_0007
Revises: 20260831_0006
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260831_0007"
down_revision: str | None = "20260831_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ocr_runs",
        sa.Column("engine_key", sa.String(length=40), server_default="paddle", nullable=False),
    )
    op.create_index(op.f("ix_ocr_runs_engine_key"), "ocr_runs", ["engine_key"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ocr_runs_engine_key"), table_name="ocr_runs")
    op.drop_column("ocr_runs", "engine_key")
