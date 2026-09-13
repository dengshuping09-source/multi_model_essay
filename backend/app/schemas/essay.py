from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.db.models import (
    EssayStatus,
    ImageQualityStatus,
    OcrInputVariant,
    OcrCorrectionStatus,
    OcrPageStatus,
    OcrRunStatus,
    SourceType,
)


class ImageQualityResponse(BaseModel):
    status: ImageQualityStatus
    quality_score: int
    blur_score: float
    brightness: float
    contrast: float
    shadow_score: float
    skew_angle: float
    rotation_degrees: int
    page_detected: bool
    warnings: list[str]
    applied_operations: list[str]
    detail: str | None
    processed_available: bool


class EssaySourceResponse(BaseModel):
    id: UUID
    source_type: SourceType
    file_name: str | None
    mime_type: str | None
    file_size_bytes: int | None
    image_width: int | None
    image_height: int | None
    sequence_no: int
    page_number: int | None
    quality: ImageQualityResponse | None


class EssaySubmissionResponse(BaseModel):
    id: UUID
    root_essay_id: UUID
    parent_essay_id: UUID | None
    version_no: int
    title: str | None
    grade_level: str | None
    genre: str | None
    writing_prompt: str | None
    full_score: int
    original_text: str | None
    status: EssayStatus
    created_at: datetime
    sources: list[EssaySourceResponse]


class EssayHistoryItemResponse(BaseModel):
    id: UUID
    root_essay_id: UUID
    parent_essay_id: UUID | None
    version_no: int
    version_count: int
    title: str | None
    grade_level: str | None
    genre: str | None
    status: EssayStatus
    created_at: datetime
    updated_at: datetime
    latest_score: float | None
    image_count: int


class EssayHistoryResponse(BaseModel):
    items: list[EssayHistoryItemResponse]


class GrowthDimensionPointResponse(BaseModel):
    essay_id: UUID
    root_essay_id: UUID
    version_no: int
    title: str | None
    evaluated_at: datetime
    score: float
    max_score: float


class GrowthDimensionTrendResponse(BaseModel):
    dimension: str
    direction: Literal["improving", "steady", "declining", "insufficient"]
    change: float | None
    recent_change: float | None
    points: list[GrowthDimensionPointResponse]


class GrowthOverallTrendResponse(BaseModel):
    direction: Literal["improving", "steady", "declining", "insufficient"]
    change: float | None
    recent_change: float | None
    points: list[GrowthDimensionPointResponse]


class GrowthIssuePatternResponse(BaseModel):
    category: str
    issue_type: str | None
    label: str
    work_count: int
    occurrence_count: int
    latest_statement: str


class GrowthImprovedIssueResponse(BaseModel):
    essay_id: UUID
    title: str | None
    previous_version_no: int
    current_version_no: int
    category: str
    issue_type: str | None
    label: str
    statement: str
    explanation: str
    evaluated_at: datetime


class GrowthRevisionSummaryResponse(BaseModel):
    comparison_count: int
    improved_count: int
    steady_count: int
    declined_count: int
    most_improved_dimension: str | None
    most_improved_dimension_count: int


class GrowthLatestEvaluationResponse(BaseModel):
    essay_id: UUID
    title: str | None
    evaluated_at: datetime
    overall_score: float | None
    dimension_scores: list[dict]


class EssayGrowthSummaryResponse(BaseModel):
    evaluation_count: int
    work_count: int
    has_long_term_insights: bool
    additional_works_needed: int
    latest: GrowthLatestEvaluationResponse | None
    recent_improvement_dimension: str | None
    practice_dimension: str | None
    practice_issue: GrowthIssuePatternResponse | None
    overall_trend: GrowthOverallTrendResponse
    dimension_trends: list[GrowthDimensionTrendResponse]
    recurring_issues: list[GrowthIssuePatternResponse]
    improved_issues: list[GrowthImprovedIssueResponse]
    revision_summary: GrowthRevisionSummaryResponse


class EssayVersionSummaryResponse(BaseModel):
    id: UUID
    root_essay_id: UUID
    parent_essay_id: UUID | None
    version_no: int
    title: str | None
    created_at: datetime
    overall_score: float | None
    dimension_scores: list[dict] | None
    summary: str | None
    top_issue: str | None


class EssayVersionHistoryResponse(BaseModel):
    root_essay_id: UUID
    current_essay_id: UUID
    items: list[EssayVersionSummaryResponse]


class EssayVersionIssueResponse(BaseModel):
    category: str
    issue_type: str | None
    statement: str
    evidence_text: str | None
    suggestion: str | None
    source: str


class EssayVersionIssueChangeResponse(BaseModel):
    previous: EssayVersionIssueResponse | None
    current: EssayVersionIssueResponse | None
    basis: Literal["matched_feedback", "changed_evidence", "new_feedback"]
    explanation: str


class EssayVersionDimensionChangeResponse(BaseModel):
    dimension: str
    before: float
    after: float
    change: float


class EssayVersionComparisonResponse(BaseModel):
    root_essay_id: UUID
    previous_essay_id: UUID
    current_essay_id: UUID
    previous_version_no: int
    current_version_no: int
    previous_score: float | None
    current_score: float | None
    score_change: float | None
    outcome: Literal["improved", "steady", "declined", "unavailable"]
    dimension_changes: list[EssayVersionDimensionChangeResponse]
    improved_issues: list[EssayVersionIssueChangeResponse]
    persistent_issues: list[EssayVersionIssueChangeResponse]
    new_issues: list[EssayVersionIssueChangeResponse]


class OcrBlockResponse(BaseModel):
    id: UUID
    reading_order: int
    text: str
    polygon: list[list[float]]
    polygon_original: list[list[float]] | None
    confidence: float | None


class OcrPageResponse(BaseModel):
    id: UUID
    source_id: UUID
    page_number: int
    status: OcrPageStatus
    input_variant: OcrInputVariant
    combined_text: str | None
    average_confidence: float | None
    block_count: int
    warnings: list[str]
    error_message: str | None
    blocks: list[OcrBlockResponse]


class OcrRunResponse(BaseModel):
    id: UUID
    essay_id: UUID
    engine_key: str
    attempt_no: int
    status: OcrRunStatus
    engine_name: str
    detection_model: str
    recognition_model: str
    combined_text: str | None
    average_confidence: float | None
    total_blocks: int
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    pages: list[OcrPageResponse]


class OcrBlockCorrectionInput(BaseModel):
    ocr_block_id: UUID
    corrected_text: str


class OcrCorrectionUpdateRequest(BaseModel):
    blocks: list[OcrBlockCorrectionInput]


class OcrCorrectionBlockResponse(BaseModel):
    ocr_block_id: UUID
    reading_order: int
    original_text: str
    corrected_text: str
    confidence: float | None
    polygon_original: list[list[float]] | None
    is_modified: bool


class OcrCorrectionPageResponse(BaseModel):
    page_result_id: UUID
    source_id: UUID
    page_number: int
    original_width: int
    original_height: int
    blocks: list[OcrCorrectionBlockResponse]


class OcrCorrectionResponse(BaseModel):
    id: UUID
    essay_id: UUID
    ocr_run_id: UUID
    status: OcrCorrectionStatus
    corrected_text: str | None
    confirmed_at: datetime | None
    pages: list[OcrCorrectionPageResponse]
