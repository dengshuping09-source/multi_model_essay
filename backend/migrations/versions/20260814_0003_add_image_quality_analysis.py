"""add image quality analysis

Revision ID: 20260814_0003
Revises: 20260814_0002
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0003"
down_revision: str | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "image_quality_analyses",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "good",
                "improvable",
                "unusable",
                name="image_quality_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("blur_score", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("brightness", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("contrast", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("shadow_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("skew_angle", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("rotation_degrees", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_detected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("page_polygon", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("applied_operations", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("processed_storage_key", sa.String(length=500), nullable=True),
        sa.Column("processed_mime_type", sa.String(length=100), nullable=True),
        sa.Column("processed_width", sa.Integer(), nullable=True),
        sa.Column("processed_height", sa.Integer(), nullable=True),
        sa.Column("processor_version", sa.String(length=50), server_default="opencv-v1", nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "processed_height IS NULL OR processed_height > 0",
            name=op.f("ck_image_quality_analyses_processed_height_positive"),
        ),
        sa.CheckConstraint(
            "processed_width IS NULL OR processed_width > 0",
            name=op.f("ck_image_quality_analyses_processed_width_positive"),
        ),
        sa.CheckConstraint(
            "quality_score >= 0 AND quality_score <= 100",
            name=op.f("ck_image_quality_analyses_quality_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["essay_sources.id"],
            name=op.f("fk_image_quality_analyses_source_id_essay_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_quality_analyses")),
        sa.UniqueConstraint("processed_storage_key", name="processed_storage_key_unique"),
        sa.UniqueConstraint("source_id", name="source_quality_analysis"),
    )
    op.create_index(
        op.f("ix_image_quality_analyses_source_id"),
        "image_quality_analyses",
        ["source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_image_quality_analyses_source_id"),
        table_name="image_quality_analyses",
    )
    op.drop_table("image_quality_analyses")

