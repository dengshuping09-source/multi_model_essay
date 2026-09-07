from __future__ import annotations

from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.db.models.common import database_enum


class ImageQualityStatus(str, Enum):
    GOOD = "good"
    IMPROVABLE = "improvable"
    UNUSABLE = "unusable"


class ImageQualityAnalysis(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "image_quality_analyses"
    __table_args__ = (
        UniqueConstraint("source_id", name="source_quality_analysis"),
        UniqueConstraint("processed_storage_key", name="processed_storage_key_unique"),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 100", name="quality_score_range"
        ),
        CheckConstraint(
            "processed_width IS NULL OR processed_width > 0",
            name="processed_width_positive",
        ),
        CheckConstraint(
            "processed_height IS NULL OR processed_height > 0",
            name="processed_height_positive",
        ),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("essay_sources.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ImageQualityStatus] = mapped_column(
        database_enum(ImageQualityStatus, "image_quality_status")
    )
    quality_score: Mapped[int] = mapped_column(Integer)
    blur_score: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    brightness: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    contrast: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    shadow_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    skew_angle: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    rotation_degrees: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    page_detected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    page_polygon: Mapped[list[list[float]] | None] = mapped_column(JSONB)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    applied_operations: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    processed_storage_key: Mapped[str | None] = mapped_column(String(500))
    processed_mime_type: Mapped[str | None] = mapped_column(String(100))
    processed_width: Mapped[int | None] = mapped_column(Integer)
    processed_height: Mapped[int | None] = mapped_column(Integer)
    original_to_processed_matrix: Mapped[list[list[float]] | None] = mapped_column(JSONB)
    processed_to_original_matrix: Mapped[list[list[float]] | None] = mapped_column(JSONB)
    processor_version: Mapped[str] = mapped_column(
        String(50), default="opencv-v1", server_default="opencv-v1"
    )
    detail: Mapped[str | None] = mapped_column(Text)

    source: Mapped[object] = relationship("EssaySource", back_populates="quality_analysis")
