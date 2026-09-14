from uuid import UUID

from decimal import Decimal

import logging

from anyio import to_thread
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import CurrentUser
from app.db.models import FinalEvaluation, ModelReview, ReferenceAssessment, ReviewBatch, ReviewRecheck, ReviewStatus
from app.db.session import get_db_session, get_session_factory
from app.modules.essays.access import get_owned_essay
from app.modules.reviews.deepseek import DeepSeekReviewError
from app.modules.reviews.polish import (
    PolishGenerationError,
    PolishProviderUnavailableError,
    generate_polish,
)
from app.modules.reports.pdf import build_report_pdf
from app.modules.reviews.service import (
    DeepAnalysisNotFoundError,
    EssayNotFoundForReviewError,
    FinalEssayTextUnavailableError,
    ReviewRecheckNotFoundError,
    ReviewRecheckUnavailableError,
    execute_review_recheck,
    execute_deep_analysis,
    get_essay_reviews,
    get_essay_review_batches,
    get_final_essay_text,
    get_latest_final_evaluation,
    get_review_batch,
    is_timeout_error,
    review_output_from_record,
    request_deep_analysis,
    run_deepseek_review,
    execute_started_review_batch,
    start_review_batch,
)
from app.schemas.review import (
    AnnotationDetailResponse,
    DeepAnalysisResponse,
    EssayPolishResponse,
    FinalEvaluationResponse,
    ModelReviewListResponse,
    ModelReviewResponse,
    ReferenceAssessmentRequest,
    ReferenceAssessmentResponse,
    RecheckEvaluationSnapshot,
    ReviewBatchRequest,
    ReviewBatchResponse,
    ReviewRecheckResponse,
)

router = APIRouter(tags=["reviews"])
logger = logging.getLogger(__name__)


async def _execute_review_batch_in_background(batch_id: UUID) -> None:
    """Use a fresh database session after the request response has returned."""
    async with get_session_factory()() as session:
        try:
            batch = await execute_started_review_batch(session, batch_id)
        except Exception:
            logger.exception("Background review batch failed", extra={"batch_id": str(batch_id)})
            batch = await get_review_batch(session, batch_id)
            batch.status = ReviewStatus.FAILED
            batch.error_message = "暂时未能生成有效评测结果，请稍后重试"
            for review in batch.reviews:
                if review.status is ReviewStatus.RUNNING:
                    review.status = ReviewStatus.FAILED
                    review.error_message = "当前评审暂时未能完成"
            await session.commit()
            return
        if batch.review_mode == "deep" and batch.status is ReviewStatus.COMPLETED:
            final = await session.scalar(
                select(FinalEvaluation)
                .where(FinalEvaluation.batch_id == batch.id)
                .order_by(FinalEvaluation.version.desc())
            )
            if final is not None:
                await execute_deep_analysis(session, final.id)


async def _execute_deep_analysis_in_background(final_evaluation_id: UUID) -> None:
    async with get_session_factory()() as session:
        try:
            await execute_deep_analysis(session, final_evaluation_id)
        except Exception:
            logger.exception(
                "Background deep analysis failed",
                extra={"final_evaluation_id": str(final_evaluation_id)},
            )


def _review_response(review: ModelReview) -> ModelReviewResponse:
    return ModelReviewResponse(
        id=review.id,
        essay_id=review.essay_id,
        model_provider=review.model_provider,
        model_name=review.model_name,
        model_version=review.model_version,
        prompt_version=review.prompt_version,
        scoring_standard_version=review.scoring_standard_version,
        retry_count=review.retry_count,
        attempt_no=review.attempt_no,
        status=review.status,
        text_source=review.text_source,
        evaluated_text=review.evaluated_text,
        overall_score=float(review.overall_score) if review.overall_score is not None else None,
        summary=review.summary,
        result=review_output_from_record(review),
        annotations=[
            AnnotationDetailResponse(
                id=item.id,
                category=item.category,
                kind=item.kind,
                severity=item.severity,
                evidence_text=item.evidence_text,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                comment=item.comment,
                suggestion=item.suggestion,
                ocr_block_id=item.ocr_block_id,
                source_id=item.ocr_block.source_id if item.ocr_block is not None else None,
                polygon_original=item.ocr_block.polygon_original if item.ocr_block is not None else None,
            )
            for item in review.annotations
        ],
        error_message=(
            "这一路评审暂时未能完成，可稍后重试"
            if review.error_message
            else None
        ),
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def _stored_polish(final: FinalEvaluation) -> EssayPolishResponse | None:
    config = final.aggregation_config if isinstance(final.aggregation_config, dict) else {}
    payload = config.get("polish")
    if not isinstance(payload, dict):
        return None
    try:
        return EssayPolishResponse.model_validate(payload)
    except ValueError:
        return None


def _stored_deep_analysis(final: FinalEvaluation) -> DeepAnalysisResponse | None:
    config = final.aggregation_config if isinstance(final.aggregation_config, dict) else {}
    payload = config.get("deep_analysis")
    if not isinstance(payload, dict):
        return None
    try:
        return DeepAnalysisResponse.model_validate(payload)
    except ValueError:
        return None


def _final_response(final: FinalEvaluation) -> FinalEvaluationResponse:
    config = final.aggregation_config if isinstance(final.aggregation_config, dict) else {}
    return FinalEvaluationResponse(
        id=final.id,
        essay_id=final.essay_id,
        batch_id=final.batch_id,
        version=final.version,
        status=final.status,
        overall_score=float(final.overall_score) if final.overall_score is not None else None,
        dimension_scores=final.dimension_scores,
        summary=final.summary,
        scoring_standard_version=final.scoring_standard_version,
        confidence=float(final.confidence) if final.confidence is not None else None,
        consistency=final.consistency,
        disputes=final.disputes,
        aggregation_config=final.aggregation_config,
        learning_feedback=(
            config.get("learning_feedback")
            if isinstance(config.get("learning_feedback"), dict)
            else None
        ),
        deep_analysis=_stored_deep_analysis(final),
        polish=_stored_polish(final),
        created_at=final.created_at,
        updated_at=final.updated_at,
    )


def _recheck_snapshot(final: FinalEvaluation | None) -> RecheckEvaluationSnapshot | None:
    if final is None:
        return None
    dimensions = final.dimension_scores if isinstance(final.dimension_scores, list) else []
    spreads = [
        float(item["spread"])
        for item in dimensions
        if isinstance(item, dict) and isinstance(item.get("spread"), (int, float))
    ]
    disputes = final.disputes if isinstance(final.disputes, list) else []
    return RecheckEvaluationSnapshot(
        id=final.id,
        version=final.version,
        overall_score=float(final.overall_score) if final.overall_score is not None else None,
        confidence=float(final.confidence) if final.confidence is not None else None,
        average_dimension_spread=(round(sum(spreads) / len(spreads), 2) if spreads else None),
        dispute_count=len(disputes),
    )


async def _recheck_response(session: AsyncSession, recheck) -> ReviewRecheckResponse:
    baseline = (
        await session.get(FinalEvaluation, recheck.final_evaluation_id)
        if recheck.final_evaluation_id
        else None
    )
    resolved = (
        await session.get(FinalEvaluation, recheck.resolved_final_evaluation_id)
        if recheck.resolved_final_evaluation_id
        else None
    )
    return ReviewRecheckResponse(
        id=recheck.id,
        status=recheck.status.value,
        trigger_reason=recheck.trigger_reason,
        requested_providers=recheck.requested_providers,
        result_summary=recheck.result_summary,
        baseline_final_evaluation_id=recheck.final_evaluation_id,
        recheck_batch_id=recheck.recheck_batch_id,
        resolved_final_evaluation_id=recheck.resolved_final_evaluation_id,
        started_at=recheck.started_at,
        completed_at=recheck.completed_at,
        baseline_evaluation=_recheck_snapshot(baseline),
        resolved_evaluation=_recheck_snapshot(resolved),
    )


async def _batch_response(session: AsyncSession, batch: ReviewBatch) -> ReviewBatchResponse:
    final = await session.scalar(
        select(FinalEvaluation).where(FinalEvaluation.batch_id == batch.id).order_by(FinalEvaluation.version.desc())
    )
    resolved_ids = [
        item.resolved_final_evaluation_id
        for item in batch.rechecks
        if item.resolved_final_evaluation_id is not None
    ]
    if resolved_ids:
        final = await session.scalar(
            select(FinalEvaluation)
            .where(FinalEvaluation.id.in_(resolved_ids))
            .order_by(FinalEvaluation.version.desc())
        ) or final
    return ReviewBatchResponse(
        id=batch.id,
        essay_id=batch.essay_id,
        requested_providers=batch.requested_providers,
        scoring_standard_version=batch.scoring_standard_version,
        review_mode=batch.review_mode if batch.review_mode in {"quick", "deep"} else "quick",
        status=batch.status,
        text_source=batch.text_source,
        error_message=batch.error_message,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        reviews=[_review_response(item) for item in sorted(batch.reviews, key=lambda item: item.created_at)],
        rechecks=[await _recheck_response(session, item) for item in batch.rechecks],
        final_evaluation=_final_response(final) if final else None,
    )


@router.post("/{essay_id}/reviews/deepseek", response_model=ModelReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_deepseek_review(
    essay_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> ModelReviewResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    try:
        review = await run_deepseek_review(session, essay_id)
    except EssayNotFoundForReviewError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FinalEssayTextUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DeepSeekReviewError as exc:
        response_status = (
            status.HTTP_504_GATEWAY_TIMEOUT if is_timeout_error(exc) else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=response_status,
            detail="当前评审服务暂时不可用，请稍后重试。你的作文已经保留。",
        ) from exc
    return _review_response(review)


@router.get("/{essay_id}/reviews", response_model=ModelReviewListResponse)
async def list_essay_reviews(
    essay_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> ModelReviewListResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    return ModelReviewListResponse(items=[_review_response(item) for item in await get_essay_reviews(session, essay_id)])


@router.post("/{essay_id}/reviews/batches", response_model=ReviewBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_review_batch(
    essay_id: UUID,
    payload: ReviewBatchRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> ReviewBatchResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    try:
        running_batch_id = await session.scalar(
            select(ReviewBatch.id)
            .where(ReviewBatch.essay_id == essay_id, ReviewBatch.status == ReviewStatus.RUNNING)
            .order_by(ReviewBatch.created_at.desc())
        )
        if running_batch_id is not None:
            return await _batch_response(session, await get_review_batch(session, running_batch_id))
        batch = await start_review_batch(
            session,
            essay_id,
            payload.providers,
            review_mode=payload.mode,
        )
    except FinalEssayTextUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    background_tasks.add_task(_execute_review_batch_in_background, batch.id)
    return await _batch_response(session, batch)


@router.get("/{essay_id}/reviews/batches", response_model=list[ReviewBatchResponse])
async def list_review_batches(
    essay_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> list[ReviewBatchResponse]:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    return [await _batch_response(session, batch) for batch in await get_essay_review_batches(session, essay_id)]


@router.post("/{essay_id}/reviews/batches/{batch_id}/retry", response_model=ReviewBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_review_batch(
    essay_id: UUID,
    batch_id: UUID,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> ReviewBatchResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    previous = await get_review_batch(session, batch_id)
    if previous.essay_id != essay_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评测任务不存在")
    running_batch_id = await session.scalar(
        select(ReviewBatch.id)
        .where(ReviewBatch.essay_id == essay_id, ReviewBatch.status == ReviewStatus.RUNNING)
        .order_by(ReviewBatch.created_at.desc())
    )
    if running_batch_id is not None:
        return await _batch_response(session, await get_review_batch(session, running_batch_id))
    batch = await start_review_batch(
        session,
        essay_id,
        previous.requested_providers,
        retry_of_batch_id=batch_id,
        review_mode=previous.review_mode,
    )
    background_tasks.add_task(_execute_review_batch_in_background, batch.id)
    return await _batch_response(session, batch)


@router.post(
    "/{essay_id}/reviews/rechecks/{recheck_id}/run",
    response_model=ReviewRecheckResponse,
)
async def run_cross_check(
    essay_id: UUID,
    recheck_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> ReviewRecheckResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    try:
        recheck = await execute_review_recheck(session, essay_id, recheck_id)
    except ReviewRecheckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewRecheckUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _recheck_response(session, recheck)


@router.get("/{essay_id}/reports/latest", response_model=FinalEvaluationResponse)
async def latest_report(
    essay_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> FinalEvaluationResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    final = await get_latest_final_evaluation(session, essay_id)
    if final is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这篇作文还没有可查看的评测报告")
    return _final_response(final)


@router.post(
    "/{essay_id}/reports/deep-analysis",
    response_model=FinalEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_deep_analysis(
    essay_id: UUID,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> FinalEvaluationResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    try:
        final, should_start = await request_deep_analysis(session, essay_id)
    except DeepAnalysisNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if should_start:
        background_tasks.add_task(_execute_deep_analysis_in_background, final.id)
    return _final_response(final)


@router.post("/{essay_id}/reports/polish", response_model=EssayPolishResponse)
async def polish_latest_report(
    essay_id: UUID,
    user: CurrentUser,
    regenerate: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> EssayPolishResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    final = await get_latest_final_evaluation(session, essay_id)
    if final is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="请先完成作文评测")
    stored = _stored_polish(final)
    if stored is not None and not regenerate:
        return stored
    try:
        final_text = await get_final_essay_text(session, essay_id)
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        ranked_suggestions: list[tuple[int, str]] = []
        for link in final.review_links:
            output = review_output_from_record(link.model_review)
            if output is None:
                continue
            ranked_suggestions.extend(
                (priority_rank[item.priority], item.suggestion)
                for item in output.improvement_suggestions
            )
        suggestions: list[str] = []
        for _, suggestion in sorted(ranked_suggestions, key=lambda item: item[0]):
            if suggestion not in suggestions:
                suggestions.append(suggestion)
        result = await generate_polish(final_text.text, final.summary, suggestions)
    except FinalEssayTextUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except PolishProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except PolishGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    response = EssayPolishResponse(
        original_text=final_text.text,
        polished_text=result.polished_text,
        text_source=final_text.source,
        overview=result.overview,
        changes=result.changes,
    )
    config = dict(final.aggregation_config) if isinstance(final.aggregation_config, dict) else {}
    config["polish"] = response.model_dump(mode="json")
    final.aggregation_config = config
    flag_modified(final, "aggregation_config")
    await session.commit()
    return response


@router.get("/{essay_id}/reports/latest.pdf", response_class=Response)
async def export_latest_report_pdf(
    essay_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    essay = await get_owned_essay(session, essay_id, user)
    if essay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    final = await get_latest_final_evaluation(session, essay_id)
    if final is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这篇作文还没有可导出的评测报告")
    rechecks = list(
        (
            await session.scalars(
                select(ReviewRecheck)
                .join(ReviewBatch, ReviewRecheck.batch_id == ReviewBatch.id)
                .where(ReviewBatch.essay_id == essay_id)
                .order_by(ReviewRecheck.started_at.asc().nulls_last())
            )
        ).all()
    )
    recheck_details = [
        (
            recheck,
            await session.get(FinalEvaluation, recheck.final_evaluation_id)
            if recheck.final_evaluation_id
            else None,
            await session.get(FinalEvaluation, recheck.resolved_final_evaluation_id)
            if recheck.resolved_final_evaluation_id
            else None,
        )
        for recheck in rechecks
    ]
    try:
        content = await to_thread.run_sync(
            build_report_pdf,
            essay,
            final,
            [link.model_review for link in final.review_links],
            recheck_details,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="报告导出组件暂不可用，请联系管理员处理。",
        ) from exc
    except Exception as exc:
        logger.exception("PDF report generation failed", extra={"essay_id": str(essay_id)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="报告暂时无法生成，请稍后重试。",
        ) from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Length": str(len(content)),
            "Cache-Control": "no-store",
            "Content-Disposition": (
                'attachment; filename="wenheng-report.pdf"; '
                "filename*=UTF-8''%E6%96%87%E8%A1%A1%E4%BD%9C%E6%96%87%E8%AF%84%E6%B5%8B%E6%8A%A5%E5%91%8A.pdf"
            )
        },
    )


@router.post("/{essay_id}/reference-assessments", response_model=ReferenceAssessmentResponse, status_code=status.HTTP_201_CREATED)
async def save_reference_assessment(
    essay_id: UUID,
    payload: ReferenceAssessmentRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> ReferenceAssessmentResponse:
    if await get_owned_essay(session, essay_id, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作文不存在")
    assessment = ReferenceAssessment(
        essay_id=essay_id,
        recorded_by_user_id=user.id,
        overall_score=Decimal(str(payload.overall_score)) if payload.overall_score is not None else None,
        dimension_scores=payload.dimension_scores,
        comments=payload.comments,
        source=payload.source,
        is_final=payload.is_final,
    )
    session.add(assessment)
    await session.commit()
    return ReferenceAssessmentResponse(
        id=assessment.id,
        essay_id=assessment.essay_id,
        overall_score=float(assessment.overall_score) if assessment.overall_score is not None else None,
        dimension_scores=assessment.dimension_scores,
        comments=assessment.comments,
        source=assessment.source,
        is_final=assessment.is_final,
        created_at=assessment.created_at,
    )
