from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.db.models.common import database_enum


class EssayStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    EVALUATED = "evaluated"


class SourceType(str, Enum):
    TEXT_INPUT = "text_input"
    IMAGE_UPLOAD = "image_upload"
    DOCUMENT_UPLOAD = "document_upload"


class OcrRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class OcrPageStatus(str, Enum):
    COMPLETED = "completed"
    LOW_CONFIDENCE = "low_confidence"
    EMPTY = "empty"
    SKIPPED_QUALITY = "skipped_quality"
    FAILED = "failed"


class OcrInputVariant(str, Enum):
    ORIGINAL = "original"
    PROCESSED = "processed"


class OcrCorrectionStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class Essay(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "essays"
    __table_args__ = (
        UniqueConstraint("root_essay_id", "version_no", name="essay_root_version"),
        CheckConstraint("version_no >= 1", name="essay_version_positive"),
    )

    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    root_essay_id: Mapped[UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), index=True
    )
    parent_essay_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("essays.id", ondelete="SET NULL"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    title: Mapped[str | None] = mapped_column(String(255))
    grade_level: Mapped[str | None] = mapped_column(String(50))
    genre: Mapped[str | None] = mapped_column(String(50))
    writing_prompt: Mapped[str | None] = mapped_column(Text)
    full_score: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    original_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EssayStatus] = mapped_column(
        database_enum(EssayStatus, "essay_status"),
        default=EssayStatus.DRAFT,
        server_default=EssayStatus.DRAFT.value,
    )

    sources: Mapped[list[EssaySource]] = relationship(
        back_populates="essay", cascade="all, delete-orphan"
    )
    sentences: Mapped[list[EssaySentence]] = relationship(
        back_populates="essay", cascade="all, delete-orphan"
    )
    model_reviews: Mapped[list[Any]] = relationship(
        "ModelReview", back_populates="essay", cascade="all, delete-orphan"
    )
    final_evaluations: Mapped[list[Any]] = relationship(
        "FinalEvaluation", back_populates="essay", cascade="all, delete-orphan"
    )
    ocr_runs: Mapped[list[OcrRun]] = relationship(
        back_populates="essay", cascade="all, delete-orphan"
    )
    ocr_corrections: Mapped[list[OcrCorrection]] = relationship(
        back_populates="essay", cascade="all, delete-orphan"
    )
    author: Mapped[Any | None] = relationship("User", back_populates="essays")
    reference_assessments: Mapped[list[Any]] = relationship(
        "ReferenceAssessment", back_populates="essay", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("root_essay_id", kwargs["id"])
        kwargs.setdefault("version_no", 1)
        super().__init__(**kwargs)


class EssaySource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "essay_sources"
    __table_args__ = (
        UniqueConstraint("essay_id", "sequence_no", name="source_sequence"),
        UniqueConstraint("storage_key", name="storage_key_unique"),
        CheckConstraint("sequence_no >= 0", name="sequence_non_negative"),
        CheckConstraint("page_number IS NULL OR page_number >= 1", name="page_positive"),
        CheckConstraint(
            "file_size_bytes IS NULL OR file_size_bytes > 0", name="file_size_positive"
        ),
        CheckConstraint(
            "image_width IS NULL OR image_width > 0", name="image_width_positive"
        ),
        CheckConstraint(
            "image_height IS NULL OR image_height > 0", name="image_height_positive"
        ),
    )

    essay_id: Mapped[UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[SourceType] = mapped_column(
        database_enum(SourceType, "source_type")
    )
    file_name: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    image_width: Mapped[int | None] = mapped_column(Integer)
    image_height: Mapped[int | None] = mapped_column(Integer)
    sequence_no: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    page_number: Mapped[int | None] = mapped_column(Integer)

    essay: Mapped[Essay] = relationship(back_populates="sources")
    ocr_blocks: Mapped[list[OcrBlock]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    quality_analysis: Mapped[Any | None] = relationship(
        "ImageQualityAnalysis",
        back_populates="source",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    ocr_page_results: Mapped[list[OcrPageResult]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class OcrRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ocr_runs"
    __table_args__ = (
        UniqueConstraint("essay_id", "attempt_no", name="essay_ocr_attempt"),
        CheckConstraint("attempt_no >= 1", name="attempt_positive"),
        CheckConstraint("total_blocks >= 0", name="total_blocks_non_negative"),
        CheckConstraint(
            "average_confidence IS NULL OR (average_confidence >= 0 AND average_confidence <= 1)",
            name="average_confidence_range",
        ),
    )

    essay_id: Mapped[UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), index=True
    )
    engine_key: Mapped[str] = mapped_column(
        String(40), default="paddle", server_default="paddle", index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[OcrRunStatus] = mapped_column(
        database_enum(OcrRunStatus, "ocr_run_status")
    )
    engine_name: Mapped[str] = mapped_column(String(80))
    detection_model: Mapped[str] = mapped_column(String(100))
    recognition_model: Mapped[str] = mapped_column(String(100))
    combined_text: Mapped[str | None] = mapped_column(Text)
    average_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    total_blocks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    essay: Mapped[Essay] = relationship(back_populates="ocr_runs")
    pages: Mapped[list[OcrPageResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    correction: Mapped[OcrCorrection | None] = relationship(
        back_populates="ocr_run", cascade="all, delete-orphan", uselist=False
    )


class OcrPageResult(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ocr_page_results"
    __table_args__ = (
        UniqueConstraint("run_id", "source_id", name="ocr_run_source"),
        UniqueConstraint("run_id", "page_number", name="ocr_run_page"),
        CheckConstraint("page_number >= 1", name="page_positive"),
        CheckConstraint("block_count >= 0", name="block_count_non_negative"),
        CheckConstraint(
            "average_confidence IS NULL OR (average_confidence >= 0 AND average_confidence <= 1)",
            name="average_confidence_range",
        ),
        CheckConstraint("input_width > 0", name="input_width_positive"),
        CheckConstraint("input_height > 0", name="input_height_positive"),
    )

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ocr_runs.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("essay_sources.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[OcrPageStatus] = mapped_column(
        database_enum(OcrPageStatus, "ocr_page_status")
    )
    input_variant: Mapped[OcrInputVariant] = mapped_column(
        database_enum(OcrInputVariant, "ocr_input_variant")
    )
    input_storage_key: Mapped[str] = mapped_column(String(500))
    input_width: Mapped[int] = mapped_column(Integer)
    input_height: Mapped[int] = mapped_column(Integer)
    input_to_original_matrix: Mapped[list[list[float]] | None] = mapped_column(JSONB)
    combined_text: Mapped[str | None] = mapped_column(Text)
    average_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    block_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    error_message: Mapped[str | None] = mapped_column(Text)

    run: Mapped[OcrRun] = relationship(back_populates="pages")
    source: Mapped[EssaySource] = relationship(back_populates="ocr_page_results")
    blocks: Mapped[list[OcrBlock]] = relationship(
        back_populates="page_result", cascade="all, delete-orphan"
    )


class OcrBlock(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ocr_blocks"
    __table_args__ = (
        UniqueConstraint("page_result_id", "block_index", name="page_result_block_index"),
        CheckConstraint("block_index >= 0", name="block_index_non_negative"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("essay_sources.id", ondelete="CASCADE"), index=True
    )
    page_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ocr_page_results.id", ondelete="CASCADE"), index=True
    )
    block_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    polygon: Mapped[list[list[float]]] = mapped_column(JSONB)
    polygon_original: Mapped[list[list[float]] | None] = mapped_column(JSONB)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    source: Mapped[EssaySource] = relationship(back_populates="ocr_blocks")
    page_result: Mapped[OcrPageResult | None] = relationship(back_populates="blocks")
    sentence_mappings: Mapped[list[SentenceOcrMapping]] = relationship(
        back_populates="ocr_block", cascade="all, delete-orphan"
    )
    corrections: Mapped[list[OcrBlockCorrection]] = relationship(
        back_populates="ocr_block", cascade="all, delete-orphan"
    )


class OcrCorrection(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ocr_corrections"
    __table_args__ = (UniqueConstraint("ocr_run_id", name="ocr_run_correction"),)

    essay_id: Mapped[UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), index=True
    )
    ocr_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ocr_runs.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[OcrCorrectionStatus] = mapped_column(
        database_enum(OcrCorrectionStatus, "ocr_correction_status"),
        default=OcrCorrectionStatus.DRAFT,
        server_default=OcrCorrectionStatus.DRAFT.value,
    )
    corrected_text: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    essay: Mapped[Essay] = relationship(back_populates="ocr_corrections")
    ocr_run: Mapped[OcrRun] = relationship(back_populates="correction")
    block_corrections: Mapped[list[OcrBlockCorrection]] = relationship(
        back_populates="correction", cascade="all, delete-orphan"
    )


class OcrBlockCorrection(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ocr_block_corrections"
    __table_args__ = (
        UniqueConstraint("correction_id", "ocr_block_id", name="correction_block"),
    )

    correction_id: Mapped[UUID] = mapped_column(
        ForeignKey("ocr_corrections.id", ondelete="CASCADE"), index=True
    )
    ocr_block_id: Mapped[UUID] = mapped_column(
        ForeignKey("ocr_blocks.id", ondelete="CASCADE"), index=True
    )
    corrected_text: Mapped[str] = mapped_column(Text)

    correction: Mapped[OcrCorrection] = relationship(back_populates="block_corrections")
    ocr_block: Mapped[OcrBlock] = relationship(back_populates="corrections")


class EssaySentence(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "essay_sentences"
    __table_args__ = (
        UniqueConstraint("essay_id", "position", name="essay_sentence_position"),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint("char_start >= 0", name="char_start_non_negative"),
        CheckConstraint("char_end > char_start", name="char_range_valid"),
    )

    essay_id: Mapped[UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)

    essay: Mapped[Essay] = relationship(back_populates="sentences")
    ocr_mappings: Mapped[list[SentenceOcrMapping]] = relationship(
        back_populates="sentence", cascade="all, delete-orphan"
    )
    annotations: Mapped[list[Any]] = relationship("AIAnnotation", back_populates="sentence")
    score_evidence: Mapped[list[Any]] = relationship("ScoreEvidence", back_populates="sentence")


class SentenceOcrMapping(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sentence_ocr_mappings"
    __table_args__ = (
        CheckConstraint(
            "sentence_start IS NULL OR sentence_start >= 0", name="sentence_start_non_negative"
        ),
        CheckConstraint(
            "sentence_end IS NULL OR sentence_end > sentence_start", name="sentence_range_valid"
        ),
        CheckConstraint("ocr_start IS NULL OR ocr_start >= 0", name="ocr_start_non_negative"),
        CheckConstraint("ocr_end IS NULL OR ocr_end > ocr_start", name="ocr_range_valid"),
    )

    sentence_id: Mapped[UUID] = mapped_column(
        ForeignKey("essay_sentences.id", ondelete="CASCADE"), index=True
    )
    ocr_block_id: Mapped[UUID] = mapped_column(
        ForeignKey("ocr_blocks.id", ondelete="CASCADE"), index=True
    )
    sentence_start: Mapped[int | None] = mapped_column(Integer)
    sentence_end: Mapped[int | None] = mapped_column(Integer)
    ocr_start: Mapped[int | None] = mapped_column(Integer)
    ocr_end: Mapped[int | None] = mapped_column(Integer)

    sentence: Mapped[EssaySentence] = relationship(back_populates="ocr_mappings")
    ocr_block: Mapped[OcrBlock] = relationship(back_populates="sentence_mappings")
