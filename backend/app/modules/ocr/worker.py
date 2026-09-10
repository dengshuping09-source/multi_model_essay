from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import multiprocessing
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Essay, OcrRun, OcrRunStatus
from app.db.session import get_session_factory
from app.modules.ocr.engine import OcrEngineKey
from app.modules.ocr.service import mark_ocr_run_failed, run_essay_ocr


logger = logging.getLogger(__name__)
ACTIVE_RUN_MARKER = Path("/app/storage/.ocr-active-run")


@dataclass(frozen=True)
class OcrJob:
    run_id: UUID
    essay_id: UUID
    engine_key: OcrEngineKey
    source_ids: set[UUID] | None


def _age_seconds(started_at: datetime) -> float:
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())


async def _fail_run(run_id: UUID) -> None:
    async with get_session_factory()() as session:
        await mark_ocr_run_failed(session, run_id)


async def _recover_interrupted_run() -> None:
    if not ACTIVE_RUN_MARKER.is_file():
        return
    try:
        run_id = UUID(ACTIVE_RUN_MARKER.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        logger.warning("discarding invalid OCR worker marker")
    else:
        logger.warning("marking interrupted OCR run as failed run_id=%s", run_id)
        await _fail_run(run_id)
    ACTIVE_RUN_MARKER.unlink(missing_ok=True)


async def _next_job() -> OcrJob | None:
    async with get_session_factory()() as session:
        run = await session.scalar(
            select(OcrRun)
            .where(OcrRun.status == OcrRunStatus.RUNNING)
            .order_by(OcrRun.started_at.asc())
            .limit(1)
            .options(
                selectinload(OcrRun.pages),
                selectinload(OcrRun.essay).selectinload(Essay.sources),
            )
        )
        if run is None:
            return None
        if _age_seconds(run.started_at) > settings.ocr_worker_stale_seconds:
            logger.warning("expiring stale OCR run run_id=%s", run.id)
            await mark_ocr_run_failed(session, run.id)
            return None

        completed_source_ids = {page.source_id for page in run.pages}
        source_ids: set[UUID] | None = None
        if completed_source_ids:
            source_ids = {
                source.id
                for source in run.essay.sources
                if source.id not in completed_source_ids
            }
            if not source_ids:
                logger.warning("OCR run has no remaining pages run_id=%s", run.id)
                await mark_ocr_run_failed(session, run.id)
                return None

        engine_key: OcrEngineKey = "baidu" if run.engine_key == "baidu" else "paddle"
        return OcrJob(
            run_id=run.id,
            essay_id=run.essay_id,
            engine_key=engine_key,
            source_ids=source_ids,
        )


def _execute_job(job: OcrJob) -> None:
    async def execute() -> None:
        async with get_session_factory()() as session:
            await run_essay_ocr(
                session,
                job.essay_id,
                engine_key=job.engine_key,
                run_id=job.run_id,
                source_ids=job.source_ids,
            )

    asyncio.run(execute())


def _run_job_process(job: OcrJob) -> int:
    ACTIVE_RUN_MARKER.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_RUN_MARKER.write_text(str(job.run_id), encoding="utf-8")
    process = multiprocessing.get_context("spawn").Process(
        target=_execute_job,
        args=(job,),
        name=f"ocr-{job.run_id}",
    )
    process.start()
    process.join(timeout=settings.ocr_worker_job_timeout_seconds)
    if process.is_alive():
        logger.error("OCR worker timeout run_id=%s", job.run_id)
        process.terminate()
        process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join(timeout=5)
    exit_code = process.exitcode if process.exitcode is not None else 1
    if exit_code == 0:
        ACTIVE_RUN_MARKER.unlink(missing_ok=True)
    return exit_code


async def run_worker() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    await _recover_interrupted_run()
    logger.info("OCR worker started")
    while True:
        job = await _next_job()
        if job is None:
            await asyncio.sleep(settings.ocr_worker_poll_seconds)
            continue
        logger.info("OCR worker accepted run_id=%s engine=%s", job.run_id, job.engine_key)
        exit_code = await asyncio.to_thread(_run_job_process, job)
        if exit_code != 0:
            logger.error("OCR worker process failed run_id=%s exit_code=%s", job.run_id, exit_code)
            await _fail_run(job.run_id)
            ACTIVE_RUN_MARKER.unlink(missing_ok=True)
        else:
            logger.info("OCR worker completed run_id=%s", job.run_id)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass
