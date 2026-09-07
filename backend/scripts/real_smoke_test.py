r"""Explicit live-service smoke test for the essay evaluation platform.

This script is deliberately outside ``backend/tests`` and never runs as part
of pytest.  It makes paid third-party requests only when the developer passes
``--confirm-live``.  It uses the real database, review providers and OCR
engines; FakeReviewProvider, StaticOcrEngine and HTTP mocks are not imported.

Examples (run from ``backend``):

    .\.venv\Scripts\python.exe scripts\real_smoke_test.py --confirm-live
    .\.venv\Scripts\python.exe scripts\real_smoke_test.py --confirm-live --image C:\\path\\to\\handwriting.jpg
"""

from __future__ import annotations

import argparse
import asyncio
import io
import mimetypes
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from anyio import to_thread
from fastapi import UploadFile
from sqlalchemy import delete
from starlette.datastructures import Headers


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.models import Essay, OcrRunStatus, User  # noqa: E402
from app.db.session import check_database_connection, get_session_factory  # noqa: E402
from app.modules.auth.service import register_user  # noqa: E402
from app.modules.essays.service import submit_essay  # noqa: E402
from app.modules.essays.storage import remove_artifact_paths  # noqa: E402
from app.modules.ocr.service import run_essay_ocr  # noqa: E402
from app.modules.reviews.providers import get_review_provider_registry  # noqa: E402
from app.modules.reviews.service import (  # noqa: E402
    get_latest_final_evaluation,
    review_output_from_record,
    run_review_batch,
)


class SmokeStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_CONFIGURED = "NOT CONFIGURED"
    NOT_VERIFIED = "NOT VERIFIED"


@dataclass(frozen=True)
class SmokeResult:
    label: str
    status: SmokeStatus
    detail: str | None = None


SHORT_ESSAY = """春天的校园里，柳树冒出了嫩芽。我和同学一起观察花坛，发现蜜蜂在花间飞舞。回到教室后，我把看到的景象写进日记，想以后继续认真观察生活。"""
PROVIDER_LABELS = {
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
    "doubao": "豆包",
}


def _safe_failure_detail(error: object | None) -> str:
    """Classify common errors without echoing responses or credentials."""
    message = str(error or "").lower()
    if "modelnotopen" in message or "model not open" in message:
        return "账号当前未开通该模型"
    if "unauthor" in message or "api key" in message or "authentication" in message:
        return "认证未通过"
    if "modelnotfound" in message or "invalidmodel" in message or "modelnotexist" in message:
        return "模型名称不可用"
    if "model or endpoint was not found" in message:
        return "模型名称或服务地址不可用"
    if "rate limit" in message or "rate limited" in message:
        return "请求频率受限"
    if "provider service failed" in message:
        return "服务暂时不可用"
    if "timeout" in message or "timed out" in message:
        return "请求超时"
    if "invalid structure" in message or "schema" in message or "validation" in message:
        return "返回结果不符合评测结构"
    if "network" in message or "connect" in message:
        return "网络连接失败"
    return "请求未成功完成"


def _configured_baidu() -> bool:
    return bool(
        settings.baidu_ocr_api_key
        and settings.baidu_ocr_api_key.get_secret_value().strip()
        and settings.baidu_ocr_secret_key
        and settings.baidu_ocr_secret_key.get_secret_value().strip()
    )


def _print_results(results: list[SmokeResult]) -> None:
    print("\n真实服务 Smoke Test")
    for result in results:
        detail = f" - {result.detail}" if result.detail else ""
        print(f"{result.label:<18} {result.status}{detail}")


def _not_verified_results(image_supplied: bool) -> list[SmokeResult]:
    image_detail = "需要提供 --image 真实作文图片" if not image_supplied else "需要传入 --confirm-live 才会调用真实服务"
    return [
        SmokeResult("数据库", SmokeStatus.NOT_VERIFIED, "需要传入 --confirm-live 才会连接"),
        SmokeResult("DeepSeek", SmokeStatus.NOT_VERIFIED, "未调用"),
        SmokeResult("Qwen", SmokeStatus.NOT_VERIFIED, "未调用"),
        SmokeResult("豆包", SmokeStatus.NOT_VERIFIED, "未调用"),
        SmokeResult("PaddleOCR", SmokeStatus.NOT_VERIFIED, image_detail),
        SmokeResult("百度 OCR", SmokeStatus.NOT_VERIFIED, image_detail),
        SmokeResult("电子作文评测", SmokeStatus.NOT_VERIFIED, "未调用"),
        SmokeResult("图片 OCR", SmokeStatus.NOT_VERIFIED, image_detail),
    ]


async def _make_upload(image_path: Path) -> UploadFile:
    image_bytes = await to_thread.run_sync(image_path.read_bytes)
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    return UploadFile(
        filename=image_path.name,
        file=io.BytesIO(image_bytes),
        headers=Headers({"content-type": mime_type}),
    )


async def _cleanup(session, user_id, essay_ids, artifact_paths: list[Path]) -> None:
    """Remove only records and uploads created by this smoke run."""
    if essay_ids:
        await session.execute(delete(Essay).where(Essay.id.in_(essay_ids)))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()
    if artifact_paths:
        await to_thread.run_sync(remove_artifact_paths, artifact_paths)


async def run_live_smoke(image_path: Path | None) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    try:
        await check_database_connection()
    except Exception:
        results.append(SmokeResult("数据库", SmokeStatus.FAIL, "无法连接 PostgreSQL"))
        results.extend(
            SmokeResult(label, SmokeStatus.NOT_VERIFIED, "数据库不可用")
            for label in ("DeepSeek", "Qwen", "豆包", "PaddleOCR", "百度 OCR", "电子作文评测", "图片 OCR")
        )
        return results
    results.append(SmokeResult("数据库", SmokeStatus.PASS))

    registry = get_review_provider_registry()
    configured_providers = {
        key: provider.status().configured for key, provider in registry.items()
    }
    artifact_paths: list[Path] = []
    essay_ids = []
    user_id = None

    try:
        async with get_session_factory()() as session:
            user = await register_user(
                session,
                email=f"real-smoke-{uuid4().hex}@local.invalid",
                display_name="Real smoke test",
                password=f"Smoke-{uuid4().hex}",
            )
            user_id = user.id
            text_essay = await submit_essay(
                session,
                author_id=user.id,
                title="真实服务冒烟测试",
                original_text=SHORT_ESSAY,
                images=[],
                grade_level="小学四年级",
                genre="记叙文",
                full_score=100,
            )
            essay_ids.append(text_essay.id)

            batch = await run_review_batch(
                session,
                text_essay.id,
                provider_keys=list(PROVIDER_LABELS),
                create_recheck=False,
            )
            reviews = {review.model_provider: review for review in batch.reviews}
            successful_reviews = 0
            for key, label in PROVIDER_LABELS.items():
                review = reviews.get(key)
                if not configured_providers.get(key):
                    results.append(SmokeResult(label, SmokeStatus.NOT_CONFIGURED))
                elif review and review_output_from_record(review) is not None:
                    successful_reviews += 1
                    results.append(SmokeResult(label, SmokeStatus.PASS))
                else:
                    results.append(
                        SmokeResult(
                            label,
                            SmokeStatus.FAIL,
                            _safe_failure_detail(review.error_message if review else None),
                        )
                    )

            final = await get_latest_final_evaluation(session, text_essay.id)
            if final is not None and final.overall_score is not None and final.dimension_scores:
                results.append(SmokeResult("电子作文评测", SmokeStatus.PASS))
            elif successful_reviews == 0 and not any(configured_providers.values()):
                results.append(SmokeResult("电子作文评测", SmokeStatus.NOT_CONFIGURED, "没有可调用的评测服务"))
            else:
                results.append(SmokeResult("电子作文评测", SmokeStatus.FAIL, "未生成有效综合报告"))

            if image_path is None:
                results.append(SmokeResult("PaddleOCR", SmokeStatus.NOT_VERIFIED, "需要提供 --image 真实作文图片"))
                results.append(SmokeResult("百度 OCR", SmokeStatus.NOT_VERIFIED, "需要提供 --image 真实作文图片"))
                results.append(SmokeResult("图片 OCR", SmokeStatus.NOT_VERIFIED, "需要提供 --image 真实作文图片"))
            else:
                image_essay = await submit_essay(
                    session,
                    author_id=user.id,
                    title="真实图片 OCR 冒烟测试",
                    original_text=None,
                    images=[await _make_upload(image_path)],
                    grade_level="小学四年级",
                    genre="记叙文",
                    full_score=100,
                )
                essay_ids.append(image_essay.id)
                for source in image_essay.sources:
                    if source.storage_key:
                        artifact_paths.append(settings.upload_dir / source.storage_key)
                    if source.quality_analysis and source.quality_analysis.processed_storage_key:
                        artifact_paths.append(settings.upload_dir / source.quality_analysis.processed_storage_key)

                paddle_run = await run_essay_ocr(session, image_essay.id, engine_key="paddle")
                # A low-confidence page is still a usable OCR result that the
                # correction screen can present. A failed/empty run is not.
                paddle_ok = (
                    paddle_run.status in {OcrRunStatus.COMPLETED, OcrRunStatus.PARTIAL}
                    and paddle_run.total_blocks > 0
                )
                results.append(
                    SmokeResult("PaddleOCR", SmokeStatus.PASS if paddle_ok else SmokeStatus.FAIL,
                                None if paddle_ok else "未保存可用 OCR 结果")
                )

                if _configured_baidu():
                    baidu_run = await run_essay_ocr(session, image_essay.id, engine_key="baidu")
                    baidu_ok = (
                        baidu_run.status in {OcrRunStatus.COMPLETED, OcrRunStatus.PARTIAL}
                        and baidu_run.total_blocks > 0
                    )
                    results.append(
                        SmokeResult("百度 OCR", SmokeStatus.PASS if baidu_ok else SmokeStatus.FAIL,
                                    None if baidu_ok else "未保存可用 OCR 结果")
                    )
                else:
                    results.append(SmokeResult("百度 OCR", SmokeStatus.NOT_CONFIGURED))

                results.append(
                    SmokeResult("图片 OCR", SmokeStatus.PASS if paddle_ok else SmokeStatus.FAIL,
                                None if paddle_ok else "PaddleOCR 未生成可用结果")
                )
    except Exception as exc:
        # A failure while creating or saving the smoke artefacts is distinct from
        # a provider failure, but must never print a possibly sensitive response.
        existing = {result.label for result in results}
        for label in ("DeepSeek", "Qwen", "豆包", "PaddleOCR", "百度 OCR", "电子作文评测", "图片 OCR"):
            if label not in existing:
                results.append(SmokeResult(label, SmokeStatus.FAIL, _safe_failure_detail(exc)))
    finally:
        if user_id is not None:
            try:
                async with get_session_factory()() as cleanup_session:
                    await _cleanup(cleanup_session, user_id, essay_ids, artifact_paths)
            except Exception:
                # Cleanup failures are intentionally not represented as a service pass.
                results.append(SmokeResult("测试清理", SmokeStatus.FAIL, "临时测试数据清理失败"))

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run explicit live service smoke checks.")
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="确认调用真实第三方服务；没有此参数时不会发起任何网络或数据库调用。",
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="一张真实作文图片。提供后会运行真实 PaddleOCR，且在配置时运行百度 OCR。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path = args.image.resolve() if args.image else None
    if image_path is not None and (not image_path.is_file() or image_path.stat().st_size == 0):
        _print_results([
            SmokeResult("图片 OCR", SmokeStatus.NOT_VERIFIED, "--image 不是有效的本地图片文件")
        ])
        return 2
    if not args.confirm_live:
        _print_results(_not_verified_results(image_path is not None))
        print("\n未调用任何真实服务。加入 --confirm-live 才会执行真实 Smoke Test。")
        return 0

    results = asyncio.run(run_live_smoke(image_path))
    _print_results(results)
    return 1 if any(result.status is SmokeStatus.FAIL for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
