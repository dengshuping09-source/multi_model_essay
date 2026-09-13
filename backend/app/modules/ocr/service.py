from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import logging
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from uuid import UUID

import numpy as np
from anyio import to_thread
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import (
    Essay,
    EssaySource,
    EssayStatus,
    ImageQualityStatus,
    OcrBlock,
    OcrInputVariant,
    OcrPageResult,
    OcrPageStatus,
    OcrRun,
    OcrRunStatus,
    SourceType,
)
from app.modules.ocr.baidu import user_facing_baidu_error
from app.modules.ocr.engine import (
    OcrEngine,
    OcrEngineKey,
    RecognizedRegion,
    get_default_ocr_engine_key,
    get_ocr_engine,
)


logger = logging.getLogger(__name__)


class EssayNotFoundError(RuntimeError):
    pass


class EssayHasNoImagesError(RuntimeError):
    pass


class OcrAlreadyRunningError(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrInput:
    variant: OcrInputVariant
    storage_key: str
    width: int
    height: int
    input_to_original_matrix: list[list[float]] | None
    path: Path


def _identity_matrix() -> list[list[float]]:
    return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _storage_path(storage_key: str) -> Path:
    root = settings.upload_dir.resolve()
    path = (root / storage_key).resolve()
    if root not in path.parents or not path.is_file():
        raise FileNotFoundError("OCR 输入图片不存在")
    return path


def _select_ocr_input(source: EssaySource) -> OcrInput:
    quality = source.quality_analysis
    if quality and quality.processed_storage_key:
        geometric_operations = {"方向纠正", "页面检测与透视矫正", "倾斜校正"}
        used_geometry = bool(geometric_operations.intersection(quality.applied_operations))
        if quality.processed_to_original_matrix or not used_geometry:
            return OcrInput(
                variant=OcrInputVariant.PROCESSED,
                storage_key=quality.processed_storage_key,
                width=quality.processed_width or source.image_width or 1,
                height=quality.processed_height or source.image_height or 1,
                input_to_original_matrix=(
                    quality.processed_to_original_matrix or _identity_matrix()
                ),
                path=_storage_path(quality.processed_storage_key),
            )
    if not source.storage_key:
        raise FileNotFoundError("OCR 原始图片不存在")
    return OcrInput(
        variant=OcrInputVariant.ORIGINAL,
        storage_key=source.storage_key,
        width=source.image_width or 1,
        height=source.image_height or 1,
        input_to_original_matrix=_identity_matrix(),
        path=_storage_path(source.storage_key),
    )


def _sort_reading_order(regions: list[RecognizedRegion]) -> list[RecognizedRegion]:
    if len(regions) < 2:
        return regions

    def bounds(region: RecognizedRegion) -> tuple[float, float, float, float]:
        xs = [point[0] for point in region.polygon]
        ys = [point[1] for point in region.polygon]
        return min(xs), min(ys), max(xs), max(ys)

    heights = [max(1.0, bounds(region)[3] - bounds(region)[1]) for region in regions]
    row_tolerance = max(8.0, median(heights) * 0.55)
    sorted_by_y = sorted(regions, key=lambda region: ((bounds(region)[1] + bounds(region)[3]) / 2, bounds(region)[0]))
    rows: list[list[RecognizedRegion]] = []
    row_centers: list[float] = []
    for region in sorted_by_y:
        region_bounds = bounds(region)
        center_y = (region_bounds[1] + region_bounds[3]) / 2
        if not rows or abs(center_y - row_centers[-1]) > row_tolerance:
            rows.append([region])
            row_centers.append(center_y)
        else:
            rows[-1].append(region)
            row_centers[-1] = mean(
                (bounds(item)[1] + bounds(item)[3]) / 2 for item in rows[-1]
            )
    return [region for row in rows for region in sorted(row, key=lambda item: bounds(item)[0])]


def _map_polygon(
    polygon: list[list[float]], matrix_values: list[list[float]] | None
) -> list[list[float]] | None:
    if matrix_values is None:
        return None
    matrix = np.asarray(matrix_values, dtype=np.float64)
    if matrix.shape != (3, 3):
        return None
    mapped: list[list[float]] = []
    for x, y in polygon:
        result = matrix @ np.array([x, y, 1.0], dtype=np.float64)
        if abs(result[2]) < 1e-9:
            return None
        mapped.append(
            [round(float(result[0] / result[2]), 2), round(float(result[1] / result[2]), 2)]
        )
    return mapped


def _decimal_confidence(value: float) -> Decimal:
    return Decimal(f"{value:.4f}")


async def _load_essay(session: AsyncSession, essay_id: UUID) -> Essay | None:
    return await session.scalar(
        select(Essay)
        .where(Essay.id == essay_id)
        .options(selectinload(Essay.sources).selectinload(EssaySource.quality_analysis))
    )


async def run_essay_ocr(
    session: AsyncSession,
    essay_id: UUID,
    engine: OcrEngine | None = None,
    engine_key: OcrEngineKey | None = None,
    *,
    run_id: UUID | None = None,
    source_ids: set[UUID] | None = None,
    defer_execution: bool = False,
) -> OcrRun:
    ocr_started = perf_counter()
    engine_key = engine_key or get_default_ocr_engine_key()
    essay = await _load_essay(session, essay_id)
    if essay is None:
        raise EssayNotFoundError
    image_sources = sorted(
        (source for source in essay.sources if source.source_type is SourceType.IMAGE_UPLOAD),
        key=lambda source: (source.page_number or 0, source.sequence_no),
    )
    if source_ids is not None:
        image_sources = [source for source in image_sources if source.id in source_ids]
    if not image_sources:
        raise EssayHasNoImagesError

    selected_engine = engine or get_ocr_engine(engine_key)
    if run_id is None:
        running = await session.scalar(
            select(OcrRun.id).where(
                OcrRun.essay_id == essay_id,
                OcrRun.status == OcrRunStatus.RUNNING,
            )
        )
        if running is not None:
            raise OcrAlreadyRunningError
        attempt_no = (
            await session.scalar(select(func.coalesce(func.max(OcrRun.attempt_no), 0)).where(OcrRun.essay_id == essay_id))
        ) + 1
        run = OcrRun(
            essay_id=essay_id,
            engine_key=engine_key,
            attempt_no=attempt_no,
            status=OcrRunStatus.RUNNING,
            engine_name=selected_engine.engine_name,
            detection_model=selected_engine.detection_model,
            recognition_model=selected_engine.recognition_model,
            pages=[],
        )
        session.add(run)
        await session.commit()
        if defer_execution:
            return run
    else:
        run = await session.scalar(select(OcrRun).where(OcrRun.id == run_id))
        if run is None or run.essay_id != essay_id:
            raise EssayNotFoundError
        run.status = OcrRunStatus.RUNNING
        run.completed_at = None
        run.error_message = None
        await session.commit()

    pages: list[OcrPageResult] = []
    for index, source in enumerate(image_sources, start=1):
        page_started = perf_counter()
        page_number = source.page_number or index
        try:
            ocr_input = _select_ocr_input(source)
        except (FileNotFoundError, ValueError) as exc:
            fallback_key = source.storage_key or "missing"
            page = OcrPageResult(
                run_id=run.id,
                source_id=source.id,
                page_number=page_number,
                status=OcrPageStatus.FAILED,
                input_variant=OcrInputVariant.ORIGINAL,
                input_storage_key=fallback_key,
                input_width=source.image_width or 1,
                input_height=source.image_height or 1,
                input_to_original_matrix=_identity_matrix(),
                error_message="这页图片暂时无法读取，请重新选择或重新拍摄。",
            )
            session.add(page)
            pages.append(page)
            await session.commit()
            logger.warning(
                "ocr_page_input_unavailable essay_id=%s run_id=%s page=%d elapsed_ms=%d",
                essay_id,
                run.id,
                page_number,
                round((perf_counter() - page_started) * 1000),
            )
            continue

        quality = source.quality_analysis
        quality_warnings = (
            list(quality.warnings)
            if quality and quality.status is ImageQualityStatus.UNUSABLE
            else []
        )

        try:
            regions = await to_thread.run_sync(selected_engine.recognize, ocr_input.path)
            regions = _sort_reading_order(regions)
            page_text = "\n".join(region.text for region in regions) or None
            confidences = [region.confidence for region in regions if region.confidence is not None]
            average_confidence = mean(confidences) if confidences else None
            if not regions:
                page_status = OcrPageStatus.EMPTY
                warnings = quality_warnings + ["当前页面未识别到文字，请确认页面不是空白且文字清晰"]
            elif average_confidence is not None and average_confidence < settings.ocr_low_confidence_threshold:
                page_status = OcrPageStatus.LOW_CONFIDENCE
                warnings = quality_warnings + ["本页平均识别置信度较低，建议核对图片清晰度和识别文字"]
            else:
                page_status = OcrPageStatus.COMPLETED
                warnings = quality_warnings

            page = OcrPageResult(
                run_id=run.id,
                source_id=source.id,
                page_number=page_number,
                status=page_status,
                input_variant=ocr_input.variant,
                input_storage_key=ocr_input.storage_key,
                input_width=ocr_input.width,
                input_height=ocr_input.height,
                input_to_original_matrix=ocr_input.input_to_original_matrix,
                combined_text=page_text,
                average_confidence=(
                    _decimal_confidence(average_confidence)
                    if average_confidence is not None
                    else None
                ),
                block_count=len(regions),
                warnings=warnings,
                blocks=[
                    OcrBlock(
                        source_id=source.id,
                        block_index=block_index,
                        text=region.text,
                        polygon=region.polygon,
                        polygon_original=_map_polygon(
                            region.polygon, ocr_input.input_to_original_matrix
                        ),
                        confidence=(
                            _decimal_confidence(region.confidence)
                            if region.confidence is not None
                            else None
                        ),
                    )
                    for block_index, region in enumerate(regions)
                ],
            )
        except Exception as exc:
            logger.exception(
                "OCR page recognition failed",
                extra={"essay_id": str(essay_id), "source_id": str(source.id), "page_number": page_number},
            )
            page = OcrPageResult(
                run_id=run.id,
                source_id=source.id,
                page_number=page_number,
                status=OcrPageStatus.FAILED,
                input_variant=ocr_input.variant,
                input_storage_key=ocr_input.storage_key,
                input_width=ocr_input.width,
                input_height=ocr_input.height,
                input_to_original_matrix=ocr_input.input_to_original_matrix,
                error_message=(
                    user_facing_baidu_error(exc)
                    if engine_key == "baidu"
                    else "当前页面暂时无法识别，请重新识别；如果仍然失败，请重新拍摄或上传更清晰的图片。"
                ),
            )
        session.add(page)
        pages.append(page)
        await session.commit()
        logger.info(
            "ocr_page_completed essay_id=%s run_id=%s engine=%s page=%d status=%s blocks=%d input=%s elapsed_ms=%d",
            essay_id,
            run.id,
            engine_key,
            page_number,
            page.status.value,
            page.block_count,
            page.input_variant.value,
            round((perf_counter() - page_started) * 1000),
        )

    if source_ids is not None:
        pages = list(
            (
                await session.scalars(
                    select(OcrPageResult)
                    .where(OcrPageResult.run_id == run.id)
                    .options(selectinload(OcrPageResult.blocks))
                )
            ).all()
        )
    text_pages = [page for page in pages if page.combined_text]
    run.combined_text = "\n\n".join(page.combined_text for page in text_pages if page.combined_text) or None
    run.total_blocks = sum(page.block_count for page in pages)
    confidences = [float(page.average_confidence) for page in pages if page.average_confidence is not None]
    run.average_confidence = _decimal_confidence(mean(confidences)) if confidences else None
    all_completed = bool(pages) and all(page.status is OcrPageStatus.COMPLETED for page in pages)
    if all_completed:
        run.status = OcrRunStatus.COMPLETED
    elif text_pages:
        run.status = OcrRunStatus.PARTIAL
        run.error_message = "部分页面未完成正常识别，请根据逐页提示检查"
    else:
        run.status = OcrRunStatus.FAILED
        # Keep the first safe page-level cause (such as configuration, timeout
        # or a provider quota) instead of hiding it behind a generic failure.
        run.error_message = next(
            (page.error_message for page in pages if page.error_message),
            "没有识别到可用的作文文字，请重新识别或换一张更清晰的图片。",
        )
    run.completed_at = datetime.now(timezone.utc)
    if run.combined_text:
        essay.status = EssayStatus.READY
    await session.commit()
    loaded_run = await session.scalar(
        select(OcrRun)
        .where(OcrRun.id == run.id)
        .options(selectinload(OcrRun.pages).selectinload(OcrPageResult.blocks))
        .execution_options(populate_existing=True)
    )
    if loaded_run is None:
        raise EssayNotFoundError
    logger.info(
        "ocr_run_completed essay_id=%s run_id=%s engine=%s status=%s pages=%d blocks=%d elapsed_ms=%d",
        essay_id,
        run.id,
        engine_key,
        run.status.value,
        len(pages),
        run.total_blocks,
        round((perf_counter() - ocr_started) * 1000),
    )
    return loaded_run


async def retry_ocr_page(
    session: AsyncSession,
    essay_id: UUID,
    run_id: UUID,
    page_id: UUID,
    *,
    defer_execution: bool = False,
) -> OcrRun:
    """Replace only one unsuccessful page while retaining all other page results."""
    run = await session.scalar(
        select(OcrRun)
        .where(OcrRun.id == run_id, OcrRun.essay_id == essay_id)
        .options(selectinload(OcrRun.pages))
    )
    if run is None:
        raise EssayNotFoundError
    if run.status is OcrRunStatus.RUNNING:
        raise OcrAlreadyRunningError
    page = next((item for item in run.pages if item.id == page_id), None)
    if page is None:
        raise EssayNotFoundError
    source_id = page.source_id
    await session.delete(page)
    run.status = OcrRunStatus.RUNNING
    run.started_at = datetime.now(timezone.utc)
    run.completed_at = None
    run.error_message = None
    await session.commit()
    if defer_execution:
        queued_run = await session.scalar(
            select(OcrRun)
            .where(OcrRun.id == run.id)
            .options(selectinload(OcrRun.pages).selectinload(OcrPageResult.blocks))
        )
        if queued_run is None:
            raise EssayNotFoundError
        return queued_run
    return await run_essay_ocr(
        session,
        essay_id,
        engine_key=run.engine_key,  # type: ignore[arg-type]
        run_id=run.id,
        source_ids={source_id},
    )


async def mark_ocr_run_failed(session: AsyncSession, run_id: UUID) -> None:
    """Ensure a background-job crash never leaves a client polling forever."""
    run = await session.scalar(select(OcrRun).where(OcrRun.id == run_id))
    if run is None or run.status is not OcrRunStatus.RUNNING:
        return
    run.status = OcrRunStatus.FAILED
    run.error_message = "识别任务暂时中断，请重新识别；已上传的图片仍然保留。"
    run.completed_at = datetime.now(timezone.utc)
    await session.commit()


async def get_latest_ocr_run(
    session: AsyncSession,
    essay_id: UUID,
    engine_key: OcrEngineKey | None = None,
) -> OcrRun | None:
    query = select(OcrRun).where(OcrRun.essay_id == essay_id)
    if engine_key is not None:
        query = query.where(OcrRun.engine_key == engine_key)
    return await session.scalar(
        query
        .order_by(OcrRun.attempt_no.desc())
        .limit(1)
        .options(selectinload(OcrRun.pages).selectinload(OcrPageResult.blocks))
    )
