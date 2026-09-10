from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from time import perf_counter
from uuid import uuid4
from uuid import UUID

from anyio import to_thread
from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import (
    Essay,
    EssaySource,
    EssayStatus,
    FinalEvaluation,
    FinalEvaluationReview,
    ImageQualityAnalysis,
    ModelReview,
    OcrRun,
    ReviewBatch,
    ReviewRecheck,
    ReviewStatus,
    SourceType,
)
from app.modules.essays.storage import (
    StoredImage,
    UploadValidationError,
    remove_artifact_paths,
    remove_essay_upload_directory,
    remove_stored_images,
    save_uploaded_image,
)
from app.modules.ocr.image_processing import ImageProcessingResult, analyze_and_preprocess_image


logger = logging.getLogger(__name__)


class EssaySubmissionError(RuntimeError):
    pass


async def discard_temporary_essay(
    session: AsyncSession, author_id: UUID, essay_id: UUID
) -> bool:
    removable = await session.scalar(
        select(Essay.id).where(
            Essay.id == essay_id,
            Essay.author_id == author_id,
            Essay.status != EssayStatus.EVALUATED,
        )
    )
    if removable is None:
        return False
    await session.execute(delete(Essay).where(Essay.id == essay_id))
    await session.commit()
    await to_thread.run_sync(remove_essay_upload_directory, settings.upload_dir, essay_id)
    return True


async def cleanup_user_session_essays(session: AsyncSession, author_id: UUID) -> None:
    """Remove abandoned work and compact completed work on a new browser session."""
    # Tasks from users who never return are also reclaimed opportunistically.
    stale_before = datetime.now(timezone.utc) - timedelta(hours=24)
    stale_ids = list(
        (
            await session.scalars(
                select(Essay.id).where(
                    Essay.status != EssayStatus.EVALUATED,
                    Essay.updated_at < stale_before,
                )
            )
        ).all()
    )
    if stale_ids:
        await session.execute(delete(Essay).where(Essay.id.in_(stale_ids)))
        await session.commit()
        for essay_id in stale_ids:
            await to_thread.run_sync(
                remove_essay_upload_directory, settings.upload_dir, essay_id
            )

    temporary_ids = list(
        (
            await session.scalars(
                select(Essay.id).where(
                    Essay.author_id == author_id,
                    Essay.status != EssayStatus.EVALUATED,
                )
            )
        ).all()
    )
    if temporary_ids:
        await session.execute(delete(Essay).where(Essay.id.in_(temporary_ids)))
        await session.commit()
        for essay_id in temporary_ids:
            await to_thread.run_sync(remove_essay_upload_directory, settings.upload_dir, essay_id)

    evaluated_ids = list(
        (
            await session.scalars(
                select(Essay.id).where(
                    Essay.author_id == author_id,
                    Essay.status == EssayStatus.EVALUATED,
                )
            )
        ).all()
    )
    for essay_id in evaluated_ids:
        finals = list(
            (
                await session.scalars(
                    select(FinalEvaluation)
                    .where(
                        FinalEvaluation.essay_id == essay_id,
                        FinalEvaluation.status == ReviewStatus.COMPLETED,
                    )
                    .order_by(FinalEvaluation.version.desc())
                )
            ).all()
        )
        if not finals:
            continue
        latest = finals[0]
        latest_config = latest.aggregation_config if isinstance(latest.aggregation_config, dict) else {}
        latest_deep_analysis = latest_config.get("deep_analysis")
        if (
            isinstance(latest_deep_analysis, dict)
            and latest_deep_analysis.get("status") in {"pending", "running"}
        ):
            # A requested deep analysis belongs to the already completed report.
            # Do not compact away its OCR/model context while it is still running.
            continue
        model_versions = list(
            (
                await session.execute(
                    select(
                        ModelReview.model_provider,
                        ModelReview.model_version,
                        ModelReview.model_name,
                    )
                    .join(
                        FinalEvaluationReview,
                        FinalEvaluationReview.model_review_id == ModelReview.id,
                    )
                    .where(FinalEvaluationReview.final_evaluation_id == latest.id)
                )
            ).all()
        )
        config = latest_config
        feedback = (
            config.get("learning_feedback")
            if isinstance(config.get("learning_feedback"), dict)
            else {}
        )
        archived_model_versions = config.get("model_versions")
        compact_model_versions = [
            {"provider": provider, "model": version or name}
            for provider, version, name in model_versions
        ]
        if not compact_model_versions and isinstance(archived_model_versions, list):
            compact_model_versions = archived_model_versions
        latest.aggregation_config = {
            "strategy": config.get("strategy"),
            "learning_feedback": {
                "strengths": list(feedback.get("strengths") or [])[:3],
                "priority_issues": list(feedback.get("priority_issues") or [])[:3],
                "excellent_expressions": [],
                "basic_expression_issues": [],
            },
            "model_versions": compact_model_versions,
            "evaluation_timing": config.get("evaluation_timing"),
            "deep_analysis": config.get("deep_analysis"),
        }
        if isinstance(latest.dimension_scores, list):
            latest.dimension_scores = [
                {
                    "dimension": item.get("dimension"),
                    "score": item.get("score"),
                    "max_score": item.get("max_score", 25),
                }
                for item in latest.dimension_scores
                if isinstance(item, dict)
            ]
        latest.disputes = []
        latest.batch_id = None

        final_ids = [item.id for item in finals]
        batch_ids = list(
            (
                await session.scalars(
                    select(ReviewBatch.id).where(ReviewBatch.essay_id == essay_id)
                )
            ).all()
        )
        await session.execute(
            delete(FinalEvaluationReview).where(
                FinalEvaluationReview.final_evaluation_id.in_(final_ids)
            )
        )
        await session.execute(
            delete(FinalEvaluation).where(
                FinalEvaluation.essay_id == essay_id,
                FinalEvaluation.id != latest.id,
            )
        )
        if batch_ids:
            await session.execute(
                delete(ReviewRecheck).where(ReviewRecheck.batch_id.in_(batch_ids))
            )
        await session.execute(delete(ModelReview).where(ModelReview.essay_id == essay_id))
        await session.execute(delete(ReviewBatch).where(ReviewBatch.essay_id == essay_id))
        await session.execute(delete(OcrRun).where(OcrRun.essay_id == essay_id))
        await session.execute(delete(EssaySource).where(EssaySource.essay_id == essay_id))
        await session.commit()
        await to_thread.run_sync(remove_essay_upload_directory, settings.upload_dir, essay_id)


async def submit_essay(
    session: AsyncSession,
    author_id: UUID,
    title: str | None,
    original_text: str | None,
    images: list[UploadFile],
    grade_level: str | None = None,
    genre: str | None = None,
    writing_prompt: str | None = None,
    full_score: int = 100,
    parent_essay_id: UUID | None = None,
) -> Essay:
    submission_started = perf_counter()
    normalized_title = (title or "").strip() or None
    normalized_text = (original_text or "").strip() or None
    normalized_grade = (grade_level or "").strip() or None
    normalized_genre = (genre or "").strip() or None
    normalized_prompt = (writing_prompt or "").strip() or None

    if not normalized_text and not images:
        raise UploadValidationError("请输入作文内容或至少上传一张作文图片")
    if normalized_title and len(normalized_title) > 255:
        raise UploadValidationError("作文标题不能超过 255 个字符")
    if normalized_text and len(normalized_text) > settings.max_essay_text_length:
        raise UploadValidationError(
            f"作文内容不能超过 {settings.max_essay_text_length} 个字符"
        )
    if full_score < 1 or full_score > 1000:
        raise UploadValidationError("The full score must be between 1 and 1000")
    if len(images) > settings.max_upload_files:
        raise UploadValidationError(f"一次最多上传 {settings.max_upload_files} 张图片")

    essay_id = uuid4()
    root_essay_id = essay_id
    version_no = 1
    if parent_essay_id is not None:
        parent = await session.scalar(
            select(Essay).where(
                Essay.id == parent_essay_id,
                Essay.author_id == author_id,
            )
        )
        if parent is None:
            raise UploadValidationError("无法基于这篇作文创建修改稿")
        root_essay_id = parent.root_essay_id or parent.id
        await session.scalar(select(Essay.id).where(Essay.id == root_essay_id).with_for_update())
        latest_version = await session.scalar(
            select(func.max(Essay.version_no)).where(Essay.root_essay_id == root_essay_id)
        )
        version_no = int(latest_version or 0) + 1
    stored_images: list[StoredImage] = []
    processing_results: list[ImageProcessingResult] = []
    processed_paths = []
    try:
        # Upload streams are saved in request order. CPU-heavy image analysis is
        # then bounded to two workers so multi-page submissions use available
        # cores without loading ten full-resolution pages simultaneously.
        for image in images:
            upload_started = perf_counter()
            stored_image = await save_uploaded_image(
                upload=image,
                essay_id=essay_id,
                upload_root=settings.upload_dir,
                max_size_bytes=settings.max_upload_size_bytes,
                max_image_pixels=settings.max_image_pixels,
            )
            stored_images.append(stored_image)

            logger.info(
                "essay_image_upload_saved essay_id=%s page=%d bytes=%d width=%d height=%d format=%s elapsed_ms=%d",
                essay_id,
                len(stored_images),
                stored_image.size_bytes,
                stored_image.width,
                stored_image.height,
                stored_image.image_format,
                round((perf_counter() - upload_started) * 1000),
            )

        preprocess_semaphore = asyncio.Semaphore(min(2, max(1, len(stored_images))))

        async def preprocess_one(index: int, stored_image: StoredImage) -> ImageProcessingResult:
            processed_path = (
                settings.upload_dir
                / str(essay_id)
                / "processed"
                / f"{uuid4().hex}.png"
            )
            preprocessing_started = perf_counter()
            async with preprocess_semaphore:
                result = await to_thread.run_sync(
                    analyze_and_preprocess_image,
                    stored_image.absolute_path,
                    processed_path,
                    settings.max_image_pixels,
                    stored_image.image_format not in {"JPEG", "PNG", "WEBP"}
                    or stored_image.is_animated,
                )
            logger.info(
                "essay_image_preprocessing_completed essay_id=%s page=%d status=%s converted=%s elapsed_ms=%d",
                essay_id,
                index,
                result.status.value,
                result.processed_path is not None,
                round((perf_counter() - preprocessing_started) * 1000),
            )
            if result.processed_path is not None:
                processed_paths.append(result.processed_path)
            return result

        if stored_images:
            preprocessing_outcomes = await asyncio.gather(
                *(
                    preprocess_one(index, stored_image)
                    for index, stored_image in enumerate(stored_images, start=1)
                ),
                return_exceptions=True,
            )
            failure = next(
                (item for item in preprocessing_outcomes if isinstance(item, BaseException)),
                None,
            )
            if failure is not None:
                raise failure
            processing_results = [
                item
                for item in preprocessing_outcomes
                if isinstance(item, ImageProcessingResult)
            ]

        sources: list[EssaySource] = []
        next_sequence = 0
        if normalized_text:
            sources.append(
                EssaySource(
                    source_type=SourceType.TEXT_INPUT,
                    sequence_no=next_sequence,
                )
            )
            next_sequence += 1

        for page_number, (stored_image, result) in enumerate(
            zip(stored_images, processing_results, strict=True), start=1
        ):
            processed_storage_key = (
                result.processed_path.relative_to(settings.upload_dir).as_posix()
                if result.processed_path
                else None
            )
            sources.append(
                EssaySource(
                    source_type=SourceType.IMAGE_UPLOAD,
                    file_name=stored_image.original_name,
                    storage_key=stored_image.storage_key,
                    mime_type=stored_image.mime_type,
                    file_size_bytes=stored_image.size_bytes,
                    image_width=stored_image.width,
                    image_height=stored_image.height,
                    sequence_no=next_sequence,
                    page_number=page_number,
                    quality_analysis=ImageQualityAnalysis(
                        status=result.status,
                        quality_score=result.quality_score,
                        blur_score=result.blur_score,
                        brightness=result.brightness,
                        contrast=result.contrast,
                        shadow_score=result.shadow_score,
                        skew_angle=result.skew_angle,
                        rotation_degrees=result.rotation_degrees,
                        page_detected=result.page_detected,
                        page_polygon=result.page_polygon,
                        warnings=result.warnings,
                        applied_operations=result.applied_operations,
                        processed_storage_key=processed_storage_key,
                        processed_mime_type="image/png" if result.processed_path else None,
                        processed_width=result.processed_width,
                        processed_height=result.processed_height,
                        original_to_processed_matrix=result.original_to_processed_matrix,
                        processed_to_original_matrix=result.processed_to_original_matrix,
                        detail=result.detail,
                    ),
                )
            )
            next_sequence += 1

        essay = Essay(
            id=essay_id,
            author_id=author_id,
            root_essay_id=root_essay_id,
            parent_essay_id=parent_essay_id,
            version_no=version_no,
            title=normalized_title,
            grade_level=normalized_grade,
            genre=normalized_genre,
            writing_prompt=normalized_prompt,
            full_score=full_score,
            original_text=normalized_text,
            status=EssayStatus.READY if normalized_text else EssayStatus.DRAFT,
            sources=sources,
        )
        session.add(essay)
        await session.commit()
        logger.info(
            "essay_submission_completed essay_id=%s images=%d has_text=%s elapsed_ms=%d",
            essay.id,
            len(stored_images),
            normalized_text is not None,
            round((perf_counter() - submission_started) * 1000),
        )
        return essay
    except UploadValidationError:
        await session.rollback()
        await to_thread.run_sync(remove_artifact_paths, processed_paths)
        await to_thread.run_sync(remove_stored_images, stored_images)
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        await to_thread.run_sync(remove_artifact_paths, processed_paths)
        await to_thread.run_sync(remove_stored_images, stored_images)
        raise EssaySubmissionError("作文信息保存失败") from exc
    except Exception as exc:
        await session.rollback()
        await to_thread.run_sync(remove_artifact_paths, processed_paths)
        await to_thread.run_sync(remove_stored_images, stored_images)
        raise EssaySubmissionError("作文提交处理失败") from exc
