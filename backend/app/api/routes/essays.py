from pathlib import Path
from collections import Counter
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.core.config import settings
from app.db.models import Essay, EssaySource, EssayStatus, FinalEvaluation, FinalEvaluationReview, OcrCorrection, OcrPageResult, OcrRun, ReviewStatus, SourceType
from app.db.session import get_db_session, get_session_factory
from app.modules.essays.service import EssaySubmissionError, discard_temporary_essay, submit_essay
from app.modules.essays.access import get_owned_essay
from app.modules.essays.growth import build_growth_summary
from app.modules.essays.storage import UploadValidationError
from app.modules.essays.version_comparison import compare_essay_versions
from app.modules.reviews.service import review_output_from_record
from app.modules.ocr.service import (
    EssayHasNoImagesError,
    EssayNotFoundError,
    OcrAlreadyRunningError,
    get_latest_ocr_run,
    mark_ocr_run_failed,
    retry_ocr_page,
    run_essay_ocr,
)
from app.modules.ocr.engine import get_default_ocr_engine_key
from app.modules.ocr.engine import OcrEngineKey
from app.modules.ocr.correction_service import (
    InvalidOcrBlockError,
    OcrCorrectionUnavailableError,
    confirm_correction,
    get_or_create_correction,
    update_correction_blocks,
)
from app.schemas.essay import (
    EssaySourceResponse,
    EssayGrowthSummaryResponse,
    EssayHistoryItemResponse,
    EssayHistoryResponse,
    EssaySubmissionResponse,
    EssayVersionHistoryResponse,
    EssayVersionComparisonResponse,
    EssayVersionSummaryResponse,
    ImageQualityResponse,
    OcrBlockResponse,
    OcrCorrectionBlockResponse,
    OcrCorrectionPageResponse,
    OcrCorrectionResponse,
    OcrCorrectionUpdateRequest,
    OcrPageResponse,
    OcrRunResponse,
)

router = APIRouter(tags=["essays"])


async def _execute_ocr_in_background(essay_id: UUID, run_id: UUID, engine: OcrEngineKey) -> None:
    """Run the persisted OCR job in a fresh request-independent session."""
    async with get_session_factory()() as background_session:
        try:
            await run_essay_ocr(background_session, essay_id, engine_key=engine, run_id=run_id)
        except Exception:
            # The run is already persisted, so the client can keep polling and
            # receive the normal per-page outcome instead of losing its upload.
            import logging
            logging.getLogger(__name__).exception("progressive OCR background job failed run_id=%s", run_id)
            await mark_ocr_run_failed(background_session, run_id)

DEMO_ESSAY = {
    "title": "雨后那盏灯",
    "grade_level": "初二",
    "genre": "记叙文",
    "full_score": 100,
    "writing_prompt": "以“雨后那盏灯”为题，写一篇记叙文。要求有具体事件、细节描写，并表达自己的感受。",
    "original_text": """傍晚的雨刚停，巷子里还积着水。我抱着没写完的作业往家走，鞋尖一碰，水面就碎成一片发亮的鱼鳞。\n\n转过旧书店时，我看见门口那盏黄灯还亮着。店主伯伯正把一箱被雨打湿的书搬进屋。他看见我，先问我有没有淋雨，又从柜台下面找出一张干纸，让我把作业本垫在上面。\n\n我本来想快点回家，可是雨声停下来以后，巷子反而显得很安静。我帮伯伯把书一本一本擦干。他说，这些书有人等着看，不能因为一场雨就丢掉。我点了点头，却没有马上明白这句话。\n\n临走时，伯伯把那张干纸折好塞进我的书包。灯光落在水面上，像一条不太清楚却一直向前的小路。回到家，我把作业写完，也想起那句“有人等着看”。后来我才明白，有些微小的照亮，并不是为了让人看见自己。""",
}


def _essay_response(essay: Essay) -> EssaySubmissionResponse:
    ordered_sources = sorted(essay.sources, key=lambda source: source.sequence_no)
    return EssaySubmissionResponse(
        id=essay.id,
        root_essay_id=essay.root_essay_id,
        parent_essay_id=essay.parent_essay_id,
        version_no=essay.version_no,
        title=essay.title,
        grade_level=essay.grade_level,
        genre=essay.genre,
        writing_prompt=essay.writing_prompt,
        full_score=essay.full_score,
        original_text=essay.original_text,
        status=essay.status,
        created_at=essay.created_at,
        sources=[
            EssaySourceResponse(
                id=source.id,
                source_type=source.source_type,
                file_name=source.file_name,
                mime_type=source.mime_type,
                file_size_bytes=source.file_size_bytes,
                image_width=source.image_width,
                image_height=source.image_height,
                sequence_no=source.sequence_no,
                page_number=source.page_number,
                quality=_quality_response(source),
            )
            for source in ordered_sources
        ],
    )


def _quality_response(source: EssaySource) -> ImageQualityResponse | None:
    if source.source_type is not SourceType.IMAGE_UPLOAD:
        return None
    quality = source.quality_analysis
    if quality is None:
        return None
    return ImageQualityResponse(
        status=quality.status,
        quality_score=quality.quality_score,
        blur_score=float(quality.blur_score),
        brightness=float(quality.brightness),
        contrast=float(quality.contrast),
        shadow_score=float(quality.shadow_score),
        skew_angle=float(quality.skew_angle),
        rotation_degrees=quality.rotation_degrees,
        page_detected=quality.page_detected,
        warnings=quality.warnings,
        applied_operations=quality.applied_operations,
        detail=quality.detail,
        processed_available=bool(quality.processed_storage_key),
    )


def _latest_completed_final(essay: Essay) -> FinalEvaluation | None:
    completed = [
        item
        for item in essay.final_evaluations
        if item.status is ReviewStatus.COMPLETED
        and item.overall_score is not None
        and item.dimension_scores is not None
    ]
    return max(completed, key=lambda item: item.version, default=None)


def _safe_storage_path(storage_key: str) -> Path:
    upload_root = settings.upload_dir.resolve()
    candidate = (upload_root / storage_key).resolve()
    if candidate != upload_root and upload_root not in candidate.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    return candidate


def _ocr_response(run: OcrRun) -> OcrRunResponse:
    pages = sorted(run.pages, key=lambda page: page.page_number)
    return OcrRunResponse(
        id=run.id,
        essay_id=run.essay_id,
        engine_key=run.engine_key,
        attempt_no=run.attempt_no,
        status=run.status,
        engine_name=run.engine_name,
        detection_model=run.detection_model,
        recognition_model=run.recognition_model,
        combined_text=run.combined_text,
        average_confidence=(
            float(run.average_confidence) if run.average_confidence is not None else None
        ),
        total_blocks=run.total_blocks,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        pages=[_ocr_page_response(page) for page in pages],
    )


def _ocr_page_response(page: OcrPageResult) -> OcrPageResponse:
    return OcrPageResponse(
        id=page.id,
        source_id=page.source_id,
        page_number=page.page_number,
        status=page.status,
        input_variant=page.input_variant,
        combined_text=page.combined_text,
        average_confidence=(
            float(page.average_confidence) if page.average_confidence is not None else None
        ),
        block_count=page.block_count,
        warnings=page.warnings,
        error_message=page.error_message,
        blocks=[
            OcrBlockResponse(
                id=block.id,
                reading_order=block.block_index,
                text=block.text,
                polygon=block.polygon,
                polygon_original=block.polygon_original,
                confidence=float(block.confidence) if block.confidence is not None else None,
            )
            for block in sorted(page.blocks, key=lambda block: block.block_index)
        ],
    )


def _correction_response(
    correction: OcrCorrection, run: OcrRun
) -> OcrCorrectionResponse:
    corrected_by_block_id = {
        item.ocr_block_id: item.corrected_text for item in correction.block_corrections
    }
    pages = sorted(run.pages, key=lambda page: page.page_number)
    return OcrCorrectionResponse(
        id=correction.id,
        essay_id=correction.essay_id,
        ocr_run_id=correction.ocr_run_id,
        status=correction.status,
        corrected_text=correction.corrected_text,
        confirmed_at=correction.confirmed_at,
        pages=[
            OcrCorrectionPageResponse(
                page_result_id=page.id,
                source_id=page.source_id,
                page_number=page.page_number,
                original_width=page.source.image_width or page.input_width,
                original_height=page.source.image_height or page.input_height,
                blocks=[
                    OcrCorrectionBlockResponse(
                        ocr_block_id=block.id,
                        reading_order=block.block_index,
                        original_text=block.text,
                        corrected_text=corrected_by_block_id.get(block.id, block.text),
                        confidence=(
                            float(block.confidence) if block.confidence is not None else None
                        ),
                        polygon_original=block.polygon_original,
                        is_modified=block.id in corrected_by_block_id,
                    )
                    for block in sorted(page.blocks, key=lambda block: block.block_index)
                ],
            )
            for page in pages
        ],
    )


@router.post("", response_model=EssaySubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_essay(
    title: Annotated[str | None, Form()] = None,
    original_text: Annotated[str | None, Form()] = None,
    grade_level: Annotated[str | None, Form()] = None,
    genre: Annotated[str | None, Form()] = None,
    writing_prompt: Annotated[str | None, Form()] = None,
    full_score: Annotated[int, Form()] = 100,
    parent_essay_id: Annotated[UUID | None, Form()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
    user: CurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> EssaySubmissionResponse:
    try:
        essay = await submit_essay(
            session=session,
            author_id=user.id,
            title=title,
            original_text=original_text,
            images=images or [],
            grade_level=grade_level,
            genre=genre,
            writing_prompt=writing_prompt,
            full_score=full_score,
            parent_essay_id=parent_essay_id,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except EssaySubmissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="作文暂时无法保存，请稍后重试",
        ) from exc

    return _essay_response(essay)


@router.post("/demo", response_model=EssaySubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_demo_essay(
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> EssaySubmissionResponse:
    """Create a real, unevaluated demo essay; model results are never pre-populated."""
    essay = await submit_essay(
        session=session,
        author_id=user.id,
        images=[],
        **DEMO_ESSAY,
    )
    return _essay_response(essay)


@router.get("", response_model=EssayHistoryResponse)
async def list_essays(
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> EssayHistoryResponse:
    essays = list(
        (
            await session.scalars(
                select(Essay)
                .where(
                    Essay.author_id == user.id,
                    Essay.status == EssayStatus.EVALUATED,
                )
                .order_by(Essay.updated_at.desc())
                .options(selectinload(Essay.sources), selectinload(Essay.final_evaluations))
            )
        ).all()
    )
    version_counts = Counter(essay.root_essay_id for essay in essays)
    return EssayHistoryResponse(
        items=[
            EssayHistoryItemResponse(
                id=essay.id,
                root_essay_id=essay.root_essay_id,
                parent_essay_id=essay.parent_essay_id,
                version_no=essay.version_no,
                version_count=version_counts[essay.root_essay_id],
                title=essay.title,
                grade_level=essay.grade_level,
                genre=essay.genre,
                status=essay.status,
                created_at=(final.created_at if (final := _latest_completed_final(essay)) is not None else essay.created_at),
                updated_at=(final.updated_at if final is not None else essay.updated_at),
                latest_score=(float(final.overall_score) if final is not None else None),
                image_count=sum(source.source_type is SourceType.IMAGE_UPLOAD for source in essay.sources),
            )
            for essay in essays
        ]
    )


@router.get("/growth/summary", response_model=EssayGrowthSummaryResponse)
async def get_growth_summary(
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> EssayGrowthSummaryResponse:
    essays = list(
        (
            await session.scalars(
                select(Essay)
                .where(
                    Essay.author_id == user.id,
                    Essay.status == EssayStatus.EVALUATED,
                )
                .order_by(Essay.created_at.asc(), Essay.version_no.asc())
                .options(selectinload(Essay.final_evaluations))
            )
        ).all()
    )
    records = [
        (essay, final)
        for essay in essays
        if (final := _latest_completed_final(essay)) is not None
    ]
    return EssayGrowthSummaryResponse.model_validate(build_growth_summary(records))


def _top_version_issue(final: FinalEvaluation | None) -> str | None:
    if final is None:
        return None
    config = final.aggregation_config if isinstance(final.aggregation_config, dict) else {}
    feedback = config.get("learning_feedback") if isinstance(config.get("learning_feedback"), dict) else {}
    archived_issues = feedback.get("priority_issues") if isinstance(feedback.get("priority_issues"), list) else []
    if archived_issues and isinstance(archived_issues[0], dict):
        suggestion = archived_issues[0].get("suggestion")
        if isinstance(suggestion, str) and suggestion.strip():
            return suggestion.strip()
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    candidates: list[tuple[int, str]] = []
    for link in final.review_links:
        output = review_output_from_record(link.model_review)
        if output is None:
            continue
        candidates.extend(
            (priority_rank[item.priority], item.suggestion)
            for item in output.improvement_suggestions
        )
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


@router.get("/{essay_id}/versions", response_model=EssayVersionHistoryResponse)
async def list_essay_versions(
    essay_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> EssayVersionHistoryResponse:
    current = await get_owned_essay(session, essay_id, user)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    versions = list(
        (
            await session.scalars(
                select(Essay)
                .where(
                    Essay.root_essay_id == current.root_essay_id,
                    Essay.author_id == user.id,
                    Essay.status == EssayStatus.EVALUATED,
                )
                .order_by(Essay.version_no.asc())
                .options(
                    selectinload(Essay.final_evaluations)
                    .selectinload(FinalEvaluation.review_links)
                    .selectinload(FinalEvaluationReview.model_review)
                )
            )
        ).all()
    )
    items: list[EssayVersionSummaryResponse] = []
    for version in versions:
        final = _latest_completed_final(version)
        items.append(
            EssayVersionSummaryResponse(
                id=version.id,
                root_essay_id=version.root_essay_id,
                parent_essay_id=version.parent_essay_id,
                version_no=version.version_no,
                title=version.title,
                created_at=version.created_at,
                overall_score=(
                    float(final.overall_score)
                    if final is not None and final.overall_score is not None
                    else None
                ),
                dimension_scores=(
                    final.dimension_scores
                    if final is not None and isinstance(final.dimension_scores, list)
                    else None
                ),
                summary=final.summary if final is not None else None,
                top_issue=_top_version_issue(final),
            )
        )
    return EssayVersionHistoryResponse(
        root_essay_id=current.root_essay_id,
        current_essay_id=current.id,
        items=items,
    )


@router.get("/{essay_id}/versions/comparison", response_model=EssayVersionComparisonResponse)
async def compare_with_previous_version(
    essay_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> EssayVersionComparisonResponse:
    current = await session.scalar(
        select(Essay)
        .where(
            Essay.id == essay_id,
            Essay.author_id == user.id,
            Essay.status == EssayStatus.EVALUATED,
        )
        .options(selectinload(Essay.final_evaluations))
    )
    if current is None or current.parent_essay_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="当前作文没有可比较的上一版。",
        )
    previous = await session.scalar(
        select(Essay)
        .where(
            Essay.id == current.parent_essay_id,
            Essay.author_id == user.id,
            Essay.status == EssayStatus.EVALUATED,
        )
        .options(selectinload(Essay.final_evaluations))
    )
    current_final = _latest_completed_final(current)
    previous_final = _latest_completed_final(previous) if previous is not None else None
    if previous is None or current_final is None or previous_final is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="当前版本缺少完整的新旧评测结果，暂时无法比较。",
        )
    return EssayVersionComparisonResponse.model_validate(
        compare_essay_versions(previous, previous_final, current, current_final)
    )


@router.get("/{essay_id}", response_model=EssaySubmissionResponse)
async def get_essay(essay_id: UUID, user: CurrentUser, session: AsyncSession = Depends(get_db_session)) -> EssaySubmissionResponse:
    essay = await get_owned_essay(session, essay_id, user)
    if essay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    return _essay_response(essay)


@router.delete("/{essay_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_temporary_essay(
    essay_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    removed = await discard_temporary_essay(session, user.id, essay_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已完成评测的作文不能作为临时任务删除",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{essay_id}/ocr",
    response_model=OcrRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def recognize_essay(
    essay_id: UUID,
    background_tasks: BackgroundTasks,
    engine: OcrEngineKey | None = Query(default=None),
    progressive: bool = Query(default=False),
    user: CurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> OcrRunResponse:
    engine = engine or get_default_ocr_engine_key()
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    try:
        if progressive or settings.ocr_worker_enabled:
            existing = await get_latest_ocr_run(session, essay_id, engine_key=engine)
            if existing is not None and existing.status.value == "running":
                return _ocr_response(existing)
            run = await run_essay_ocr(session, essay_id, engine_key=engine, defer_execution=True)
            if not settings.ocr_worker_enabled:
                background_tasks.add_task(_execute_ocr_in_background, essay_id, run.id, engine)
        else:
            run = await run_essay_ocr(session, essay_id, engine_key=engine)
    except EssayNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在") from exc
    except EssayHasNoImagesError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="这篇作文没有可供 OCR 识别的图片",
        ) from exc
    except OcrAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="这篇作文正在识别中") from exc
    return _ocr_response(run)


@router.get("/{essay_id}/ocr", response_model=OcrRunResponse)
async def get_essay_ocr(
    essay_id: UUID,
    engine: OcrEngineKey | None = Query(default=None),
    user: CurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> OcrRunResponse:
    engine = engine or get_default_ocr_engine_key()
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    run = await get_latest_ocr_run(session, essay_id, engine_key=engine)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚无 OCR 识别结果")
    return _ocr_response(run)


@router.post("/{essay_id}/ocr/runs/{run_id}/pages/{page_id}/retry", response_model=OcrRunResponse)
async def retry_essay_ocr_page(
    essay_id: UUID,
    run_id: UUID,
    page_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> OcrRunResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    try:
        return _ocr_response(
            await retry_ocr_page(
                session,
                essay_id,
                run_id,
                page_id,
                defer_execution=settings.ocr_worker_enabled,
            )
        )
    except OcrAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="这篇作文仍在识别中，请稍后再试") from exc
    except EssayNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到需要重新识别的页面") from exc


@router.get("/{essay_id}/ocr/correction", response_model=OcrCorrectionResponse)
async def get_ocr_correction(
    essay_id: UUID,
    ocr_run_id: UUID | None = Query(default=None),
    user: CurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> OcrCorrectionResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    try:
        correction, run = await get_or_create_correction(session, essay_id, ocr_run_id)
    except OcrCorrectionUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _correction_response(correction, run)


@router.put("/{essay_id}/ocr/correction", response_model=OcrCorrectionResponse)
async def save_ocr_correction(
    essay_id: UUID,
    payload: OcrCorrectionUpdateRequest,
    ocr_run_id: UUID | None = Query(default=None),
    user: CurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> OcrCorrectionResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    updates = {item.ocr_block_id: item.corrected_text for item in payload.blocks}
    if len(updates) != len(payload.blocks):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="同一个 OCR 文字区域不能重复提交",
        )
    try:
        correction, run = await update_correction_blocks(session, essay_id, updates, ocr_run_id)
    except OcrCorrectionUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidOcrBlockError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _correction_response(correction, run)


@router.post("/{essay_id}/ocr/correction/confirm", response_model=OcrCorrectionResponse)
async def confirm_ocr_correction(
    essay_id: UUID,
    ocr_run_id: UUID | None = Query(default=None),
    user: CurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> OcrCorrectionResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    try:
        correction, run = await confirm_correction(session, essay_id, ocr_run_id)
    except OcrCorrectionUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _correction_response(correction, run)


@router.get("/sources/{source_id}/images/{variant}", response_class=FileResponse)
async def get_source_image(
    source_id: UUID,
    variant: Literal["original", "processed"],
    user: CurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    source = await session.scalar(
        select(EssaySource)
        .join(Essay, EssaySource.essay_id == Essay.id)
        .where(EssaySource.id == source_id, Essay.author_id == user.id)
        .options(selectinload(EssaySource.quality_analysis))
    )
    if source is None or source.source_type is not SourceType.IMAGE_UPLOAD:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")

    if variant == "original":
        storage_key = source.storage_key
        mime_type = source.mime_type
    else:
        quality = source.quality_analysis
        storage_key = quality.processed_storage_key if quality else None
        mime_type = quality.processed_mime_type if quality else None

    if not storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    return FileResponse(_safe_storage_path(storage_key), media_type=mime_type or "image/png")
