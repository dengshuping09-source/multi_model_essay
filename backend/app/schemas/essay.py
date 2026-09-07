from datetime import datetime
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
