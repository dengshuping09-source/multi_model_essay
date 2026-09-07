from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    OcrBlock,
    OcrBlockCorrection,
    OcrCorrection,
    OcrCorrectionStatus,
    OcrPageResult,
    OcrRun,
)


class OcrCorrectionUnavailableError(RuntimeError):
    pass


class InvalidOcrBlockError(ValueError):
    pass


def _ordered_blocks(run: OcrRun) -> list[OcrBlock]:
    return [
        block
        for page in sorted(run.pages, key=lambda item: item.page_number)
        for block in sorted(page.blocks, key=lambda item: item.block_index)
    ]


def compose_corrected_text(
    run: OcrRun, corrected_by_block_id: dict[UUID, str]
) -> str | None:
    page_texts: list[str] = []
    for page in sorted(run.pages, key=lambda item: item.page_number):
        blocks = sorted(page.blocks, key=lambda item: item.block_index)
        text = "\n".join(
            corrected_by_block_id.get(block.id, block.text) for block in blocks
        )
        if text:
            page_texts.append(text)
    return "\n\n".join(page_texts) or None


async def _load_latest_run(
    session: AsyncSession, essay_id: UUID, ocr_run_id: UUID | None = None
) -> OcrRun | None:
    query = select(OcrRun).where(OcrRun.essay_id == essay_id)
    if ocr_run_id is not None:
        query = query.where(OcrRun.id == ocr_run_id)
    return await session.scalar(
        query
        .order_by(OcrRun.attempt_no.desc())
        .limit(1)
        .execution_options(populate_existing=True)
        .options(
            selectinload(OcrRun.pages).selectinload(OcrPageResult.source),
            selectinload(OcrRun.pages).selectinload(OcrPageResult.blocks),
            selectinload(OcrRun.correction).selectinload(OcrCorrection.block_corrections),
        )
    )


async def get_or_create_correction(
    session: AsyncSession, essay_id: UUID, ocr_run_id: UUID | None = None
) -> tuple[OcrCorrection, OcrRun]:
    run = await _load_latest_run(session, essay_id, ocr_run_id)
    if run is None:
        raise OcrCorrectionUnavailableError("尚无可校对的 OCR 结果")
    if not run.pages:
        raise OcrCorrectionUnavailableError("OCR 没有可校对的页面")

    correction = run.correction
    if correction is None:
        correction = OcrCorrection(
            essay_id=essay_id,
            ocr_run_id=run.id,
            status=OcrCorrectionStatus.DRAFT,
            corrected_text=compose_corrected_text(run, {}),
        )
        session.add(correction)
        await session.commit()
        # The API response is built after this function returns, outside
        # SQLAlchemy's async greenlet boundary. Populate the collection now so
        # serialisation never relies on lazy relationship access.
        await session.refresh(correction, attribute_names=["block_corrections"])
    return correction, run


async def update_correction_blocks(
    session: AsyncSession,
    essay_id: UUID,
    updates: dict[UUID, str],
    ocr_run_id: UUID | None = None,
) -> tuple[OcrCorrection, OcrRun]:
    correction, run = await get_or_create_correction(session, essay_id, ocr_run_id)
    blocks = {block.id: block for block in _ordered_blocks(run)}
    invalid_ids = set(updates).difference(blocks)
    if invalid_ids:
        raise InvalidOcrBlockError("校对内容包含不属于当前 OCR 结果的文字区域")

    existing = {item.ocr_block_id: item for item in correction.block_corrections}
    for block_id, corrected_text in updates.items():
        original_text = blocks[block_id].text
        current = existing.get(block_id)
        if corrected_text == original_text:
            if current is not None:
                session.delete(current)
                existing.pop(block_id, None)
            continue
        if current is None:
            current = OcrBlockCorrection(
                correction_id=correction.id,
                ocr_block_id=block_id,
                corrected_text=corrected_text,
            )
            session.add(current)
            existing[block_id] = current
        else:
            current.corrected_text = corrected_text

    corrected_by_block_id = {
        block_id: item.corrected_text for block_id, item in existing.items()
    }
    correction.corrected_text = compose_corrected_text(run, corrected_by_block_id)
    correction.status = OcrCorrectionStatus.DRAFT
    correction.confirmed_at = None
    await session.commit()
    return await get_or_create_correction(session, essay_id, run.id)


async def confirm_correction(
    session: AsyncSession, essay_id: UUID, ocr_run_id: UUID | None = None
) -> tuple[OcrCorrection, OcrRun]:
    correction, run = await get_or_create_correction(session, essay_id, ocr_run_id)
    corrected_by_block_id = {
        item.ocr_block_id: item.corrected_text for item in correction.block_corrections
    }
    correction.corrected_text = compose_corrected_text(run, corrected_by_block_id)
    correction.status = OcrCorrectionStatus.CONFIRMED
    correction.confirmed_at = datetime.now(timezone.utc)
    await session.commit()
    return await get_or_create_correction(session, essay_id, run.id)
