from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import (
    AIAnnotation,
    Essay,
    EssayStatus,
    FinalEvaluation,
    FinalEvaluationReview,
    ModelReview,
    OcrCorrection,
    OcrCorrectionStatus,
    OcrPageResult,
    OcrBlock,
    OcrBlockCorrection,
    RecheckStatus,
    ReviewBatch,
    ReviewRecheck,
    ReviewStatus,
    ReferenceAssessment,
    ScoreEvidence,
)
from app.modules.reviews.analysis import aggregate_outputs
from app.modules.reviews.contracts import EssayReviewOutput
from app.modules.reviews.deepseek import (
    PROMPT_VERSION,
    DeepSeekReviewError,
    DeepSeekTimeoutError,
    ProviderReviewResult,
    get_deepseek_client,
)
from app.modules.reviews.providers import ProviderUnavailableError, get_review_provider_registry
from app.modules.reviews.standards import EssayReviewContext, PROMPT_VERSION as STANDARD_PROMPT_VERSION, SCORING_STANDARD_VERSION

DEEPSEEK_PROVIDER = "deepseek"


class EssayNotFoundForReviewError(RuntimeError):
    pass


class FinalEssayTextUnavailableError(RuntimeError):
    pass


class ReviewRecheckNotFoundError(RuntimeError):
    pass


class ReviewRecheckUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class FinalEssayText:
    text: str
    source: str
    ocr_correction_id: UUID | None = None
    ocr_run_id: UUID | None = None


@dataclass(frozen=True)
class CalibrationResult:
    weights: dict[str, float] | None
    sample_counts: dict[str, int]
    mean_absolute_errors: dict[str, float]


def _normalized_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def get_final_essay_text(session: AsyncSession, essay_id: UUID) -> FinalEssayText:
    essay = await session.scalar(
        select(Essay)
        .where(Essay.id == essay_id)
        .options(selectinload(Essay.ocr_corrections))
    )
    if essay is None:
        raise EssayNotFoundForReviewError("Essay does not exist")

    confirmed_corrections = [
        correction
        for correction in essay.ocr_corrections
        if correction.status is OcrCorrectionStatus.CONFIRMED
        and _normalized_text(correction.corrected_text) is not None
    ]
    if confirmed_corrections:
        latest = max(
            confirmed_corrections,
            key=lambda item: item.confirmed_at or datetime.min.replace(tzinfo=timezone.utc),
        )
        return FinalEssayText(
            text=_normalized_text(latest.corrected_text) or "",
            source="ocr_corrected",
            ocr_correction_id=latest.id,
            ocr_run_id=latest.ocr_run_id,
        )

    direct_text = _normalized_text(essay.original_text)
    if direct_text is not None:
        return FinalEssayText(text=direct_text, source="direct_input")
    raise FinalEssayTextUnavailableError(
        "A confirmed OCR correction or directly entered essay text is required for review"
    )


def _resolve_quote_offsets(
    essay_text: str,
    quote: str,
    start_offset: int | None,
    end_offset: int | None,
) -> tuple[int | None, int | None]:
    if (
        start_offset is not None
        and end_offset is not None
        and end_offset <= len(essay_text)
        and essay_text[start_offset:end_offset] == quote
    ):
        return start_offset, end_offset
    located_at = essay_text.find(quote)
    if located_at < 0:
        return None, None
    return located_at, located_at + len(quote)


async def _next_attempt_no(session: AsyncSession, essay_id: UUID, model_name: str) -> int:
    latest_attempt = await session.scalar(
        select(func.max(ModelReview.attempt_no)).where(
            ModelReview.essay_id == essay_id,
            ModelReview.model_provider == DEEPSEEK_PROVIDER,
            ModelReview.model_name == model_name,
        )
    )
    return int(latest_attempt or 0) + 1


async def _load_review(session: AsyncSession, review_id: UUID) -> ModelReview:
    review = await session.scalar(
        select(ModelReview)
        .where(ModelReview.id == review_id)
        .options(
            selectinload(ModelReview.annotations).selectinload(AIAnnotation.ocr_block),
            selectinload(ModelReview.score_evidence),
        )
    )
    if review is None:
        raise RuntimeError("Saved review could not be reloaded")
    return review


def _review_raw_response(result: ProviderReviewResult) -> dict[str, object]:
    return {
        "output": result.output.model_dump(mode="json"),
        "provider_response_id": result.provider_response_id,
        "usage": result.usage,
    }


async def run_deepseek_review(session: AsyncSession, essay_id: UUID) -> ModelReview:
    final_text = await get_final_essay_text(session, essay_id)
    model_name = settings.deepseek_model
    review = ModelReview(
        essay_id=essay_id,
        model_provider=DEEPSEEK_PROVIDER,
        model_name=model_name,
        prompt_version=PROMPT_VERSION,
        attempt_no=await _next_attempt_no(session, essay_id, model_name),
        status=ReviewStatus.RUNNING,
        text_source=final_text.source,
        evaluated_text=final_text.text,
    )
    session.add(review)
    await session.commit()

    try:
        result = await get_deepseek_client().review(final_text.text)
        output = result.output
        review.status = ReviewStatus.COMPLETED
        review.model_version = result.model_name
        review.overall_score = Decimal(str(output.overall_score))
        review.dimension_scores = [item.model_dump(mode="json") for item in output.dimension_scores]
        review.summary = output.summary
        review.raw_response = _review_raw_response(result)
        review.error_message = None

        for item in output.annotations:
            start_offset, end_offset = _resolve_quote_offsets(
                final_text.text, item.quote, item.start_offset, item.end_offset
            )
            session.add(
                AIAnnotation(
                    model_review_id=review.id,
                    category=item.category,
                    kind=item.kind,
                    severity=item.severity,
                    evidence_text=item.quote,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    comment=item.comment,
                    suggestion=item.suggestion,
                )
            )

        for dimension in output.dimension_scores:
            for evidence in dimension.evidence:
                session.add(
                    ScoreEvidence(
                        model_review_id=review.id,
                        dimension=dimension.dimension,
                        evidence_text=evidence.quote,
                        rationale=evidence.rationale,
                        score_value=Decimal(str(dimension.score)),
                    )
                )
        await session.commit()
        return await _load_review(session, review.id)
    except DeepSeekReviewError as exc:
        review.status = ReviewStatus.FAILED
        review.error_message = str(exc)
        review.raw_response = None
        await session.commit()
        raise


async def get_essay_reviews(session: AsyncSession, essay_id: UUID) -> list[ModelReview]:
    return list(
        (
            await session.scalars(
                select(ModelReview)
                .where(ModelReview.essay_id == essay_id)
                .order_by(ModelReview.created_at.desc())
                .options(
                    selectinload(ModelReview.annotations).selectinload(AIAnnotation.ocr_block),
                    selectinload(ModelReview.score_evidence),
                )
            )
        ).all()
    )


def review_output_from_record(review: ModelReview) -> EssayReviewOutput | None:
    if review.status is not ReviewStatus.COMPLETED or not isinstance(review.raw_response, dict):
        return None
    output = review.raw_response.get("output")
    if not isinstance(output, dict):
        return None
    try:
        return EssayReviewOutput.model_validate(output)
    except ValueError:
        return None


def is_timeout_error(error: DeepSeekReviewError) -> bool:
    return isinstance(error, DeepSeekTimeoutError)


async def _next_provider_attempt_no(
    session: AsyncSession, essay_id: UUID, provider_key: str, model_name: str
) -> int:
    latest_attempt = await session.scalar(
        select(func.max(ModelReview.attempt_no)).where(
            ModelReview.essay_id == essay_id,
            ModelReview.model_provider == provider_key,
            ModelReview.model_name == model_name,
        )
    )
    return int(latest_attempt or 0) + 1


async def _matching_ocr_block_id(
    session: AsyncSession, final_text: FinalEssayText, quote: str
) -> UUID | None:
    if final_text.ocr_run_id is None:
        return None
    rows = await session.execute(
        select(OcrBlock, OcrBlockCorrection)
        .join(OcrPageResult, OcrBlock.page_result_id == OcrPageResult.id)
        .outerjoin(
            OcrBlockCorrection,
            (OcrBlockCorrection.ocr_block_id == OcrBlock.id)
            & (OcrBlockCorrection.correction_id == final_text.ocr_correction_id),
        )
        .where(OcrPageResult.run_id == final_text.ocr_run_id)
        .order_by(OcrPageResult.page_number, OcrBlock.block_index)
    )
    for block, correction in rows:
        candidate_text = correction.corrected_text if correction is not None else block.text
        if quote and quote in candidate_text:
            return block.id
    return None


async def _persist_provider_output(
    session: AsyncSession,
    review: ModelReview,
    result: ProviderReviewResult,
    final_text: FinalEssayText,
) -> None:
    output = result.output
    review.status = ReviewStatus.COMPLETED
    review.model_version = result.model_name
    review.overall_score = Decimal(str(output.overall_score))
    review.dimension_scores = [item.model_dump(mode="json") for item in output.dimension_scores]
    review.summary = output.summary
    review.raw_response = _review_raw_response(result)
    review.error_message = None
    for item in output.annotations:
        start_offset, end_offset = _resolve_quote_offsets(
            final_text.text, item.quote, item.start_offset, item.end_offset
        )
        session.add(
            AIAnnotation(
                model_review_id=review.id,
                ocr_block_id=await _matching_ocr_block_id(session, final_text, item.quote),
                category=item.category,
                kind=item.kind,
                severity=item.severity,
                evidence_text=item.quote,
                start_offset=start_offset,
                end_offset=end_offset,
                comment=item.comment,
                suggestion=item.suggestion,
            )
        )
    for dimension in output.dimension_scores:
        for evidence in dimension.evidence:
            session.add(
                ScoreEvidence(
                    model_review_id=review.id,
                    dimension=dimension.dimension,
                    evidence_text=evidence.quote,
                    rationale=evidence.rationale,
                    score_value=Decimal(str(dimension.score)),
                )
            )


async def _call_provider_with_retry(provider, final_text: FinalEssayText, context: EssayReviewContext):
    last_error: DeepSeekReviewError | None = None
    for retry_count in range(settings.model_review_max_retries + 1):
        try:
            result = await asyncio.wait_for(
                provider.review(final_text.text, context), timeout=settings.model_review_timeout_seconds
            )
            return result, retry_count, None
        except asyncio.TimeoutError:
            last_error = DeepSeekTimeoutError(f"{provider.display_name} review request timed out")
        except DeepSeekReviewError as exc:
            last_error = exc
        except asyncio.CancelledError:
            raise
        except Exception:
            # Keep an unexpected provider-side failure isolated to this one
            # independent review instead of cancelling the entire batch.
            last_error = DeepSeekReviewError(f"{provider.display_name} review request failed")
    return None, settings.model_review_max_retries, last_error or DeepSeekReviewError("Review failed")


async def _calibrated_provider_weights(
    session: AsyncSession, provider_keys: list[str]
) -> CalibrationResult:
    """Return frozen reliability weights only when every active provider has enough teacher data."""
    references = list(
        (
            await session.scalars(
                select(ReferenceAssessment)
                .where(
                    ReferenceAssessment.is_final.is_(True),
                    ReferenceAssessment.overall_score.is_not(None),
                )
                .order_by(ReferenceAssessment.created_at.desc())
            )
        ).all()
    )
    errors: dict[str, list[float]] = {key: [] for key in provider_keys}
    for reference in references:
        reviews = list(
            (
                await session.scalars(
                    select(ModelReview)
                    .where(
                        ModelReview.essay_id == reference.essay_id,
                        ModelReview.model_provider.in_(provider_keys),
                        ModelReview.status == ReviewStatus.COMPLETED,
                        ModelReview.overall_score.is_not(None),
                    )
                    .order_by(ModelReview.updated_at.desc())
                )
            ).all()
        )
        seen: set[str] = set()
        for review in reviews:
            if review.model_provider in seen:
                continue
            seen.add(review.model_provider)
            errors[review.model_provider].append(
                abs(float(review.overall_score) - float(reference.overall_score))
            )
    sample_counts = {key: len(values) for key, values in errors.items()}
    mean_absolute_errors = {
        key: round(mean(values), 4) for key, values in errors.items() if values
    }
    if not provider_keys or any(
        sample_counts[key] < settings.model_calibration_min_samples for key in provider_keys
    ):
        return CalibrationResult(None, sample_counts, mean_absolute_errors)
    inverse_errors = {
        key: 1.0 / max(mean_absolute_errors[key], 0.25) for key in provider_keys
    }
    average_weight = sum(inverse_errors.values()) / len(inverse_errors)
    return CalibrationResult(
        {key: round(value / average_weight, 6) for key, value in inverse_errors.items()},
        sample_counts,
        mean_absolute_errors,
    )


async def start_review_batch(
    session: AsyncSession,
    essay_id: UUID,
    provider_keys: list[str] | None = None,
    retry_of_batch_id: UUID | None = None,
) -> ReviewBatch:
    final_text = await get_final_essay_text(session, essay_id)
    essay = await session.get(Essay, essay_id)
    if essay is None:
        raise EssayNotFoundForReviewError("Essay does not exist")
    registry = get_review_provider_registry()
    requested = list(dict.fromkeys(provider_keys or ["deepseek", "qwen", "doubao"]))
    unknown = [key for key in requested if key not in registry]
    if unknown:
        raise ValueError(f"Unknown review provider: {unknown[0]}")
    batch = ReviewBatch(
        essay_id=essay_id,
        requested_providers=requested,
        scoring_standard_version=SCORING_STANDARD_VERSION,
        status=ReviewStatus.RUNNING,
        text_source=final_text.source,
        evaluated_text=final_text.text,
        retry_of_batch_id=retry_of_batch_id,
    )
    session.add(batch)
    await session.flush()
    for key in requested:
        provider = registry[key]
        state = provider.status()
        review = ModelReview(
            essay_id=essay_id,
            batch_id=batch.id,
            model_provider=key,
            model_name=state.model_name,
            prompt_version=STANDARD_PROMPT_VERSION,
            scoring_standard_version=SCORING_STANDARD_VERSION,
            attempt_no=await _next_provider_attempt_no(session, essay_id, key, state.model_name),
            status=ReviewStatus.RUNNING if state.configured else ReviewStatus.FAILED,
            text_source=final_text.source,
            evaluated_text=final_text.text,
            error_message=None if state.configured else state.detail,
        )
        session.add(review)
    await session.commit()

    # The batch and each independent review now exist durably before a remote
    # request begins. HTTP callers can return this state and poll it while a
    # background worker executes the requests.
    return await get_review_batch(session, batch.id)

async def execute_started_review_batch(
    session: AsyncSession,
    batch_id: UUID,
    *,
    create_recheck: bool = True,
) -> ReviewBatch:
    """Execute a persisted batch and expose each completed view immediately."""
    batch = await get_review_batch(session, batch_id)
    if batch.status is not ReviewStatus.RUNNING:
        return batch

    essay = await session.get(Essay, batch.essay_id)
    if essay is None:
        raise EssayNotFoundForReviewError("Essay does not exist")
    registry = get_review_provider_registry()
    final_text = FinalEssayText(text=batch.evaluated_text, source=batch.text_source)
    context = EssayReviewContext(essay.grade_level, essay.genre, essay.writing_prompt, essay.full_score)
    reviews = {review.model_provider: review for review in batch.reviews}
    available = [
        (key, registry[key])
        for key, review in reviews.items()
        if review.status is ReviewStatus.RUNNING
        and key in registry
        and registry[key].status().configured
    ]

    async def evaluate_one(key: str, provider):
        return key, await _call_provider_with_retry(provider, final_text, context)

    # All remote calls are started at once. Their results are written in
    # completion order so the polling API can accurately report 1/3, 2/3, etc.
    tasks = [asyncio.create_task(evaluate_one(key, provider)) for key, provider in available]
    for task in asyncio.as_completed(tasks):
        key, (result, retry_count, error) = await task
        review = reviews[key]
        review.retry_count = retry_count
        if result is not None:
            await _persist_provider_output(session, review, result, final_text)
        else:
            review.status = ReviewStatus.FAILED
            review.error_message = str(error)
            review.raw_response = None
        await session.commit()

    completed = [
        review
        for review in reviews.values()
        if review.status is ReviewStatus.COMPLETED
        and review_output_from_record(review) is not None
    ]
    batch.status = ReviewStatus.COMPLETED if completed else ReviewStatus.FAILED
    batch.error_message = None if completed else "暂时未能生成有效评测结果，请稍后重试"
    await session.commit()
    if completed:
        await _create_final_evaluation(
            session,
            essay,
            batch,
            completed,
            len(batch.requested_providers),
            create_recheck=create_recheck,
        )
    return await get_review_batch(session, batch.id)


async def run_review_batch(
    session: AsyncSession,
    essay_id: UUID,
    provider_keys: list[str] | None = None,
    retry_of_batch_id: UUID | None = None,
    create_recheck: bool = True,
) -> ReviewBatch:
    """Synchronous service wrapper retained for CLI and offline tests."""
    batch = await start_review_batch(session, essay_id, provider_keys, retry_of_batch_id)
    return await execute_started_review_batch(
        session, batch.id, create_recheck=create_recheck
    )


async def _create_final_evaluation(
    session: AsyncSession,
    essay: Essay,
    batch: ReviewBatch,
    completed: list[ModelReview],
    expected_count: int,
    create_recheck: bool = True,
) -> FinalEvaluation:
    version = int(
        await session.scalar(select(func.coalesce(func.max(FinalEvaluation.version), 0)).where(FinalEvaluation.essay_id == essay.id))
        or 0
    ) + 1
    outputs = [
        (review.model_provider, output)
        for review in completed
        if (output := review_output_from_record(review)) is not None
    ]
    if not outputs:
        raise RuntimeError("Structured review output disappeared before aggregation")
    final = FinalEvaluation(
        essay_id=essay.id,
        batch_id=batch.id,
        version=version,
        status=ReviewStatus.COMPLETED,
        scoring_standard_version=SCORING_STANDARD_VERSION,
        aggregation_config={},
    )
    session.add(final)
    await session.flush()
    calibration = await _calibrated_provider_weights(
        session, [provider_key for provider_key, _ in outputs]
    )
    aggregate = aggregate_outputs(outputs, expected_count, calibration.weights)
    final.overall_score = Decimal(str(aggregate.overall_score))
    final.dimension_scores = aggregate.dimensions
    final.summary = aggregate.summary
    final.confidence = Decimal(str(aggregate.confidence))
    final.consistency = aggregate.consistency
    final.disputes = aggregate.disputes
    final.aggregation_config = {
        "strategy": (
            "teacher_calibrated_inverse_mae_v1"
            if calibration.weights is not None
            else "equal_weight_mean_v1"
        ),
        "outlier_distance": 10,
        "dispute_spread": 8,
        "provider_weights": calibration.weights,
        "calibration_min_samples": settings.model_calibration_min_samples,
        "calibration_sample_counts": calibration.sample_counts,
        "calibration_mean_absolute_errors": calibration.mean_absolute_errors,
        "confidence_factors": aggregate.confidence_factors,
        "learning_feedback": aggregate.learning_feedback,
        "model_versions": [
            {
                "provider": review.model_provider,
                "model": review.model_version or review.model_name,
            }
            for review in completed
        ],
    }
    for review in completed:
        session.add(FinalEvaluationReview(final_evaluation_id=final.id, model_review_id=review.id, weight=Decimal("1")))
    if create_recheck and aggregate.disputes:
        session.add(
            ReviewRecheck(
                batch_id=batch.id,
                final_evaluation_id=final.id,
                status=RecheckStatus.PENDING,
                trigger_reason="High score disagreement or outlier detected",
                requested_providers=batch.requested_providers,
                result_summary="Awaiting a configured cross-check provider.",
            )
        )
    # The database row acts as a temporary processing task until this point.
    # Promote only a fully aggregated essay into formal history and retain the
    # exact text that was actually evaluated (including confirmed OCR edits).
    essay.original_text = batch.evaluated_text
    essay.status = EssayStatus.EVALUATED
    await session.commit()
    return final


async def execute_review_recheck(
    session: AsyncSession, essay_id: UUID, recheck_id: UUID
) -> ReviewRecheck:
    recheck = await session.scalar(
        select(ReviewRecheck)
        .join(ReviewBatch, ReviewRecheck.batch_id == ReviewBatch.id)
        .where(ReviewRecheck.id == recheck_id, ReviewBatch.essay_id == essay_id)
    )
    if recheck is None:
        raise ReviewRecheckNotFoundError("Review recheck does not exist")
    if recheck.status is RecheckStatus.RUNNING:
        raise ReviewRecheckUnavailableError("Review recheck is already running")
    if recheck.status is RecheckStatus.COMPLETED:
        return recheck

    recheck.status = RecheckStatus.RUNNING
    recheck.started_at = datetime.now(timezone.utc)
    recheck.result_summary = "Cross-check review is running."
    await session.commit()
    try:
        recheck_batch = await run_review_batch(
            session,
            essay_id,
            recheck.requested_providers,
            retry_of_batch_id=recheck.batch_id,
            create_recheck=False,
        )
        resolved_final = await session.scalar(
            select(FinalEvaluation)
            .where(FinalEvaluation.batch_id == recheck_batch.id)
            .order_by(FinalEvaluation.version.desc())
        )
        baseline_final = (
            await session.get(FinalEvaluation, recheck.final_evaluation_id)
            if recheck.final_evaluation_id
            else None
        )
        recheck.recheck_batch_id = recheck_batch.id
        recheck.resolved_final_evaluation_id = resolved_final.id if resolved_final else None
        recheck.completed_at = datetime.now(timezone.utc)
        if resolved_final is None or resolved_final.status is ReviewStatus.FAILED:
            recheck.status = RecheckStatus.FAILED
            recheck.result_summary = "Cross-check completed without a usable structured result."
        else:
            recheck.status = RecheckStatus.COMPLETED
            baseline_score = (
                float(baseline_final.overall_score)
                if baseline_final and baseline_final.overall_score is not None
                else None
            )
            resolved_score = (
                float(resolved_final.overall_score)
                if resolved_final.overall_score is not None
                else None
            )
            recheck.result_summary = (
                f"Cross-check completed: baseline {baseline_score if baseline_score is not None else '--'}, "
                f"recheck {resolved_score if resolved_score is not None else '--'}."
            )
        await session.commit()
    except (FinalEssayTextUnavailableError, ValueError) as exc:
        recheck.status = RecheckStatus.FAILED
        recheck.completed_at = datetime.now(timezone.utc)
        recheck.result_summary = str(exc)
        await session.commit()
    return recheck


async def get_review_batch(session: AsyncSession, batch_id: UUID) -> ReviewBatch:
    batch = await session.scalar(
        select(ReviewBatch)
        .where(ReviewBatch.id == batch_id)
        .options(selectinload(ReviewBatch.reviews).selectinload(ModelReview.annotations).selectinload(AIAnnotation.ocr_block), selectinload(ReviewBatch.rechecks))
    )
    if batch is None:
        raise RuntimeError("Review batch does not exist")
    return batch


async def get_essay_review_batches(session: AsyncSession, essay_id: UUID) -> list[ReviewBatch]:
    return list(
        (
            await session.scalars(
                select(ReviewBatch)
                .where(ReviewBatch.essay_id == essay_id)
                .order_by(ReviewBatch.created_at.desc())
                .options(selectinload(ReviewBatch.reviews).selectinload(ModelReview.annotations).selectinload(AIAnnotation.ocr_block), selectinload(ReviewBatch.rechecks))
            )
        ).all()
    )


async def get_latest_final_evaluation(session: AsyncSession, essay_id: UUID) -> FinalEvaluation | None:
    return await session.scalar(
        select(FinalEvaluation)
        .where(
            FinalEvaluation.essay_id == essay_id,
            FinalEvaluation.status == ReviewStatus.COMPLETED,
            FinalEvaluation.overall_score.is_not(None),
            FinalEvaluation.dimension_scores.is_not(None),
        )
        .order_by(FinalEvaluation.version.desc())
        .options(selectinload(FinalEvaluation.review_links).selectinload(FinalEvaluationReview.model_review).selectinload(ModelReview.annotations).selectinload(AIAnnotation.ocr_block))
    )


def provider_statuses():
    return [provider.status() for provider in get_review_provider_registry().values()]

