from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.db.models.common import JsonObject, database_enum


class ReviewStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RecheckStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ReviewBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_batches"

    essay_id: Mapped[UUID] = mapped_column(ForeignKey("essays.id", ondelete="CASCADE"), index=True)
    requested_providers: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    scoring_standard_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[ReviewStatus] = mapped_column(database_enum(ReviewStatus, "review_batch_status"))
    text_source: Mapped[str] = mapped_column(String(40))
    evaluated_text: Mapped[str] = mapped_column(Text)
    retry_of_batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("review_batches.id", ondelete="SET NULL"))
    error_message: Mapped[str | None] = mapped_column(Text)

    essay: Mapped[object] = relationship("Essay")
    reviews: Mapped[list[ModelReview]] = relationship(back_populates="batch")
    rechecks: Mapped[list[ReviewRecheck]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        foreign_keys="ReviewRecheck.batch_id",
    )


class ModelReview(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_reviews"
    __table_args__ = (
        UniqueConstraint(
            "essay_id", "model_provider", "model_name", "attempt_no", name="model_attempt"
        ),
        CheckConstraint("attempt_no >= 1", name="attempt_positive"),
    )

    essay_id: Mapped[UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("review_batches.id", ondelete="SET NULL"), index=True)
    model_provider: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(150))
    model_version: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    scoring_standard_version: Mapped[str | None] = mapped_column(String(100))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[ReviewStatus] = mapped_column(
        database_enum(ReviewStatus, "review_status"),
        default=ReviewStatus.PENDING,
        server_default=ReviewStatus.PENDING.value,
    )
    text_source: Mapped[str] = mapped_column(
        String(40), default="direct_input", server_default="direct_input"
    )
    evaluated_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dimension_scores: Mapped[JsonObject | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[JsonObject | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)

    essay: Mapped[object] = relationship("Essay", back_populates="model_reviews")
    batch: Mapped[ReviewBatch | None] = relationship(back_populates="reviews")
    annotations: Mapped[list[AIAnnotation]] = relationship(
        back_populates="model_review", cascade="all, delete-orphan"
    )
    score_evidence: Mapped[list[ScoreEvidence]] = relationship(
        back_populates="model_review", cascade="all, delete-orphan"
    )
    final_links: Mapped[list[FinalEvaluationReview]] = relationship(
        back_populates="model_review", cascade="all, delete-orphan"
    )


class AIAnnotation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_annotations"
    __table_args__ = (
        CheckConstraint("start_offset IS NULL OR start_offset >= 0", name="start_non_negative"),
        CheckConstraint("end_offset IS NULL OR end_offset > start_offset", name="offset_range_valid"),
    )

    model_review_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_reviews.id", ondelete="CASCADE"), index=True
    )
    sentence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("essay_sentences.id", ondelete="SET NULL"), index=True
    )
    ocr_block_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ocr_blocks.id", ondelete="SET NULL"), index=True
    )
    category: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20), default="improvement", server_default="improvement")
    severity: Mapped[str | None] = mapped_column(String(30))
    evidence_text: Mapped[str | None] = mapped_column(Text)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)

    model_review: Mapped[ModelReview] = relationship(back_populates="annotations")
    sentence: Mapped[object | None] = relationship("EssaySentence", back_populates="annotations")
    ocr_block: Mapped[object | None] = relationship("OcrBlock")
    score_evidence: Mapped[list[ScoreEvidence]] = relationship(back_populates="annotation")


class ScoreEvidence(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "score_evidence"

    model_review_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_reviews.id", ondelete="CASCADE"), index=True
    )
    sentence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("essay_sentences.id", ondelete="SET NULL"), index=True
    )
    annotation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_annotations.id", ondelete="SET NULL"), index=True
    )
    dimension: Mapped[str] = mapped_column(String(80))
    evidence_text: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    score_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    model_review: Mapped[ModelReview] = relationship(back_populates="score_evidence")
    sentence: Mapped[object | None] = relationship("EssaySentence", back_populates="score_evidence")
    annotation: Mapped[AIAnnotation | None] = relationship(back_populates="score_evidence")


class FinalEvaluation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "final_evaluations"
    __table_args__ = (
        UniqueConstraint("essay_id", "version", name="essay_final_version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    essay_id: Mapped[UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("review_batches.id", ondelete="SET NULL"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[ReviewStatus] = mapped_column(
        database_enum(ReviewStatus, "final_evaluation_status"),
        default=ReviewStatus.PENDING,
        server_default=ReviewStatus.PENDING.value,
    )
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dimension_scores: Mapped[JsonObject | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)
    scoring_standard_version: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    consistency: Mapped[str | None] = mapped_column(String(30))
    disputes: Mapped[JsonObject | None] = mapped_column(JSONB)
    aggregation_config: Mapped[JsonObject | None] = mapped_column(JSONB)

    essay: Mapped[object] = relationship("Essay", back_populates="final_evaluations")
    review_links: Mapped[list[FinalEvaluationReview]] = relationship(
        back_populates="final_evaluation", cascade="all, delete-orphan"
    )


class FinalEvaluationReview(Base):
    __tablename__ = "final_evaluation_reviews"

    final_evaluation_id: Mapped[UUID] = mapped_column(
        ForeignKey("final_evaluations.id", ondelete="CASCADE"), primary_key=True
    )
    model_review_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_reviews.id", ondelete="CASCADE"), primary_key=True
    )
    weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))

    final_evaluation: Mapped[FinalEvaluation] = relationship(back_populates="review_links")
    model_review: Mapped[ModelReview] = relationship(back_populates="final_links")


class ReviewRecheck(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_rechecks"

    batch_id: Mapped[UUID] = mapped_column(ForeignKey("review_batches.id", ondelete="CASCADE"), index=True)
    final_evaluation_id: Mapped[UUID | None] = mapped_column(ForeignKey("final_evaluations.id", ondelete="SET NULL"), index=True)
    recheck_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review_batches.id", ondelete="SET NULL"), index=True
    )
    resolved_final_evaluation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("final_evaluations.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[RecheckStatus] = mapped_column(database_enum(RecheckStatus, "review_recheck_status"))
    trigger_reason: Mapped[str] = mapped_column(Text)
    requested_providers: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    result_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped[ReviewBatch] = relationship(
        back_populates="rechecks", foreign_keys=[batch_id]
    )


class ReferenceAssessment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reference_assessments"

    essay_id: Mapped[UUID] = mapped_column(ForeignKey("essays.id", ondelete="CASCADE"), index=True)
    recorded_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dimension_scores: Mapped[JsonObject | None] = mapped_column(JSONB)
    comments: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="teacher", server_default="teacher")
    is_final: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    essay: Mapped[object] = relationship("Essay", back_populates="reference_assessments")
