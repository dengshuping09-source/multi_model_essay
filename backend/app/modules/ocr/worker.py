from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import multiprocessing
from pathlib import Path
from queue import Empty
from time import monotonic
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Essay, OcrRun, OcrRunStatus
from app.db.session import get_session_factory
from app.modules.ocr.engine import OcrEngineKey


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
        run = await session.scalar(select(OcrRun).where(OcrRun.id == run_id))
        if run is None or run.status is not OcrRunStatus.RUNNING:
            return
        run.status = OcrRunStatus.FAILED
        run.error_message = "识别任务暂时中断，请重新识别；已上传的图片仍然保留。"
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()


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
            run.status = OcrRunStatus.FAILED
            run.error_message = "识别任务等待时间过长，请重新识别；已上传的图片仍然保留。"
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
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
                run.status = OcrRunStatus.FAILED
                run.error_message = "没有需要继续识别的图片，请重新提交识别。"
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return None

        engine_key: OcrEngineKey = "baidu" if run.engine_key == "baidu" else "paddle"
        return OcrJob(
            run_id=run.id,
            essay_id=run.essay_id,
            engine_key=engine_key,
            source_ids=source_ids,
        )


async def _execute_job(job: OcrJob) -> None:
    # Keep numpy/OpenCV/Paddle imports out of the lightweight supervisor. They
    # belong in the isolated child, which leaves considerably more of the
    # container memory limit available for the OCR model itself.
    from app.modules.ocr.service import run_essay_ocr

    async with get_session_factory()() as session:
        await run_essay_ocr(
            session,
            job.essay_id,
            engine_key=job.engine_key,
            run_id=job.run_id,
            source_ids=job.source_ids,
        )


def _consume_jobs(job_queue, result_queue) -> None:
    """Run OCR jobs in one isolated process so the loaded model can be reused.

    The parent process still owns timeout and crash recovery.  If Paddle hangs or
    exceeds the worker container's memory limit, only this child is replaced and
    the web API remains available.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    async def consume() -> None:
        while True:
            job = await asyncio.to_thread(job_queue.get)
            if job is None:
                return
            try:
                await _execute_job(job)
            except Exception:
                logger.exception("OCR worker child job failed run_id=%s", job.run_id)
                result_queue.put((str(job.run_id), 1, "job_error"))
            else:
                result_queue.put((str(job.run_id), 0, "completed"))

    asyncio.run(consume())


class OcrProcessRunner:
    """Supervise a reusable OCR child while retaining a hard per-job timeout."""

    def __init__(self) -> None:
        self._context = multiprocessing.get_context("spawn")
        self._process = None
        self._job_queue = None
        self._result_queue = None
        self._completed_jobs = 0

    def _start(self) -> None:
        self._job_queue = self._context.Queue(maxsize=1)
        self._result_queue = self._context.Queue(maxsize=1)
        self._process = self._context.Process(
            target=_consume_jobs,
            args=(self._job_queue, self._result_queue),
            name="ocr-engine",
        )
        self._process.start()
        self._completed_jobs = 0
        logger.info("OCR engine process started pid=%s", self._process.pid)

    def _stop(self, *, force: bool) -> None:
        process = self._process
        if process is None:
            return
        if process.is_alive() and not force and self._job_queue is not None:
            try:
                self._job_queue.put(None, timeout=1)
            except Exception:
                force = True
            else:
                process.join(timeout=8)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        for queue in (self._job_queue, self._result_queue):
            if queue is not None:
                if force:
                    queue.cancel_join_thread()
                queue.close()
                if not force:
                    queue.join_thread()
        self._process = None
        self._job_queue = None
        self._result_queue = None

    def execute(self, job: OcrJob) -> tuple[int, str]:
        if self._process is None or not self._process.is_alive():
            self._stop(force=True)
            self._start()
        assert self._process is not None
        assert self._job_queue is not None
        assert self._result_queue is not None

        ACTIVE_RUN_MARKER.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_RUN_MARKER.write_text(str(job.run_id), encoding="utf-8")
        self._job_queue.put(job)
        deadline = monotonic() + settings.ocr_worker_job_timeout_seconds
        while monotonic() < deadline:
            remaining = max(0.01, min(0.5, deadline - monotonic()))
            try:
                run_id, exit_code, reason = self._result_queue.get(timeout=remaining)
            except Empty:
                if not self._process.is_alive():
                    exit_code = self._process.exitcode or 1
                    self._stop(force=True)
                    return exit_code, "process_exited"
                continue
            if run_id != str(job.run_id):
                logger.warning(
                    "discarding unexpected OCR worker result expected=%s actual=%s",
                    job.run_id,
                    run_id,
                )
                continue
            if exit_code == 0:
                ACTIVE_RUN_MARKER.unlink(missing_ok=True)
                self._completed_jobs += 1
                if self._completed_jobs >= max(1, settings.ocr_worker_max_jobs_per_process):
                    logger.info(
                        "recycling OCR engine process after %d jobs",
                        self._completed_jobs,
                    )
                    self._stop(force=False)
            return int(exit_code), str(reason)

        logger.error("OCR worker timeout run_id=%s", job.run_id)
        self._stop(force=True)
        return 1, "timeout"

    def close(self) -> None:
        self._stop(force=False)


async def run_worker() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    await _recover_interrupted_run()
    logger.info("OCR worker started")
    runner = OcrProcessRunner()
    try:
        while True:
            job = await _next_job()
            if job is None:
                await asyncio.sleep(settings.ocr_worker_poll_seconds)
                continue
            logger.info("OCR worker accepted run_id=%s engine=%s", job.run_id, job.engine_key)
            exit_code, reason = await asyncio.to_thread(runner.execute, job)
            if exit_code != 0:
                logger.error(
                    "OCR worker process failed run_id=%s exit_code=%s reason=%s",
                    job.run_id,
                    exit_code,
                    reason,
                )
                await _fail_run(job.run_id)
                ACTIVE_RUN_MARKER.unlink(missing_ok=True)
            else:
                logger.info("OCR worker completed run_id=%s", job.run_id)
    finally:
        runner.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass
