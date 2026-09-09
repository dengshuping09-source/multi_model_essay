from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.db.models import ReviewStatus
from app.modules.reviews.contracts import EssayReviewOutput, PolishChange


class ModelReviewResponse(BaseModel):
    id: UUID
    essay_id: UUID
    model_provider: str
    model_name: str
    model_version: str | None
    prompt_version: str | None
    scoring_standard_version: str | None
    retry_count: int
    attempt_no: int
    status: ReviewStatus
    text_source: str
    evaluated_text: str
    overall_score: float | None
    summary: str | None
    result: EssayReviewOutput | None
    annotations: list["AnnotationDetailResponse"]
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class AnnotationDetailResponse(BaseModel):
    id: UUID
    category: str
    kind: str = "improvement"
    severity: str | None
    evidence_text: str | None
    start_offset: int | None
    end_offset: int | None
    comment: str
    suggestion: str | None
    ocr_block_id: UUID | None
    source_id: UUID | None
    polygon_original: list[list[float]] | None


class ModelReviewListResponse(BaseModel):
    items: list[ModelReviewResponse]


class ProviderStatusResponse(BaseModel):
    key: str
    display_name: str
    model_name: str
    configured: bool
    detail: str


class ServiceStatusResponse(BaseModel):
    key: str
    kind: str
    display_name: str
    configured: bool
    available: bool
    detail: str
    model_name: str | None = None


class ReviewBatchRequest(BaseModel):
    providers: list[str] = Field(default_factory=lambda: ["deepseek", "qwen", "doubao"], min_length=1, max_length=3)
    mode: Literal["quick", "deep"] = "quick"


class DeepAnalysisResponse(BaseModel):
    status: Literal["not_started", "pending", "running", "completed", "failed"]
    requested_mode: Literal["quick", "deep"] = "quick"
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    overall_analysis: str | None = None
    annotations: list[dict[str, Any]] = Field(default_factory=list)
    dimension_details: list[dict[str, Any]] = Field(default_factory=list)
    basic_expression_issues: list[dict[str, Any]] = Field(default_factory=list)


class RecheckEvaluationSnapshot(BaseModel):
    id: UUID
    version: int
    overall_score: float | None
    confidence: float | None
    average_dimension_spread: float | None
    dispute_count: int


class ReviewRecheckResponse(BaseModel):
    id: UUID
    status: str
    trigger_reason: str
    requested_providers: list[str]
    result_summary: str | None
    baseline_final_evaluation_id: UUID | None
    recheck_batch_id: UUID | None
    resolved_final_evaluation_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    baseline_evaluation: RecheckEvaluationSnapshot | None = None
    resolved_evaluation: RecheckEvaluationSnapshot | None = None


class FinalEvaluationResponse(BaseModel):
    id: UUID
    essay_id: UUID
    batch_id: UUID | None
    version: int
    status: ReviewStatus
    overall_score: float | None
    dimension_scores: list[dict[str, Any]] | None
    summary: str | None
    scoring_standard_version: str | None
    confidence: float | None
    consistency: str | None
    disputes: list[dict[str, Any]] | None
    aggregation_config: dict[str, Any] | None
    learning_feedback: dict[str, Any] | None = None
    deep_analysis: DeepAnalysisResponse | None = None
    polish: "EssayPolishResponse | None" = None
    created_at: datetime
    updated_at: datetime


class ReviewBatchResponse(BaseModel):
    id: UUID
    essay_id: UUID
    requested_providers: list[str]
    scoring_standard_version: str
    review_mode: Literal["quick", "deep"] = "quick"
    status: ReviewStatus
    text_source: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    reviews: list[ModelReviewResponse]
    rechecks: list[ReviewRecheckResponse]
    final_evaluation: FinalEvaluationResponse | None


class EssayPolishResponse(BaseModel):
    original_text: str
    polished_text: str
    text_source: str
    overview: str
    changes: list[PolishChange]


class ReferenceAssessmentRequest(BaseModel):
    overall_score: float | None = Field(default=None, ge=0, le=1000)
    dimension_scores: list[dict[str, Any]] | None = None
    comments: str | None = Field(default=None, max_length=4000)
    source: str = Field(default="teacher", max_length=40)
    is_final: bool = True


class ReferenceAssessmentResponse(BaseModel):
    id: UUID
    essay_id: UUID
    overall_score: float | None
    dimension_scores: list[dict[str, Any]] | None
    comments: str | None
    source: str
    is_final: bool
    created_at: datetime
