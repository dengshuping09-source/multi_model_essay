from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import UUID, uuid4

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db.models import Essay, EssaySource, FinalEvaluation, ModelReview, User
from app.db.session import get_engine, get_session_factory
from app.main import app
from app.modules.ocr.engine import RecognizedRegion
from app.modules.reviews.contracts import (
    DimensionScore,
    EssayReviewOutput,
    EvidenceItem,
    ImprovementSuggestion,
    ReviewAnnotation,
)
from app.modules.reviews.deepseek import ProviderReviewResult
from app.modules.reviews.providers import ProviderStatus


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)

ESSAY_TEXT = "The autumn wind crossed the playground. I slowed down and noticed the golden leaves."


def document_image() -> np.ndarray:
    image = np.full((760, 560, 3), 248, dtype=np.uint8)
    cv2.rectangle(image, (22, 18), (538, 740), (210, 210, 210), 3)
    for y in range(75, 700, 36):
        cv2.line(image, (58, y), (505, y), (65, 65, 65), 3)
    return image


def encode_image(extension: str) -> bytes:
    ok, payload = cv2.imencode(extension, document_image())
    assert ok
    return payload.tobytes()


def structured_review(score: float = 86) -> EssayReviewOutput:
    dimensions = [
        ("content_and_ideas", 22, "The scene is focused."),
        ("structure_and_coherence", 22, "The ideas follow a clear order."),
        ("language_and_expression", 21, "The language is clear and concrete."),
        ("writing_conventions", 21, "The sentences and punctuation are consistent."),
    ]
    return EssayReviewOutput(
        overall_score=score,
        summary="The essay presents a clear scene and can become stronger with one more sensory detail.",
        dimension_scores=[
            DimensionScore(
                dimension=dimension,
                score=value,
                max_score=25,
                rationale=rationale,
                evidence=[EvidenceItem(quote="golden leaves", rationale="This is a concrete detail.")],
            )
            for dimension, value, rationale in dimensions
        ],
        annotations=[
            ReviewAnnotation(
                category="expression",
                severity="medium",
                quote="golden leaves",
                comment="The image is clear, but the feeling could be developed.",
                suggestion="Add a sound or movement to complete the moment.",
            )
        ],
        improvement_suggestions=[
            ImprovementSuggestion(
                priority="high",
                category="expression",
                suggestion="Add one sensory detail after the final sentence.",
                example_revision="The leaves rustled softly beside my shoes.",
            )
        ],
    )


class StaticOcrEngine:
    engine_name = "test-ocr"
    detection_model = "test-det"
    recognition_model = "test-rec"

    def recognize(self, _: Path) -> list[RecognizedRegion]:
        return [
            RecognizedRegion(
                ESSAY_TEXT,
                [[38, 72], [500, 72], [500, 116], [38, 116]],
                0.96,
            )
        ]


class FailOnceOcrEngine(StaticOcrEngine):
    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, path: Path) -> list[RecognizedRegion]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("internal OCR adapter secret")
        return super().recognize(path)


class FakeReviewProvider:
    def __init__(self, key: str, *, configured: bool = True, score: float = 86) -> None:
        self.key = key
        self.display_name = f"Test {key}"
        self.model_name = f"test-{key}-model"
        self.configured = configured
        self.score = score

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            key=self.key,
            display_name=self.display_name,
            model_name=self.model_name,
            configured=self.configured,
            detail="ready" if self.configured else "API_KEY is not configured",
        )

    async def review(self, _: str, __: object) -> ProviderReviewResult:
        return ProviderReviewResult(
            output=structured_review(self.score),
            provider_response_id=f"response-{self.key}",
            model_name=self.model_name,
            usage={"total_tokens": 100},
        )


def provider_registry(*, configured: bool = True) -> dict[str, FakeReviewProvider]:
    return {
        key: FakeReviewProvider(key, configured=configured, score=score)
        for key, score in (("deepseek", 86), ("qwen", 86), ("doubao", 86))
    }


async def authenticate(client: AsyncClient) -> UUID:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": f"core-flow-{uuid4()}@example.com",
            "display_name": "Core flow test",
            "password": "test-password-2026",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    client.headers["Authorization"] = f"Bearer {payload['access_token']}"
    return UUID(payload["user"]["id"])


async def cleanup_records(essay_ids: list[UUID], user_id: UUID | None) -> None:
    async with get_session_factory()() as session:
        if essay_ids:
            await session.execute(delete(Essay).where(Essay.id.in_(essay_ids)))
        if user_id is not None:
            await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


def configure_test_database(tmp_path: Path) -> None:
    settings.database_url = TEST_DATABASE_URL
    settings.upload_dir = tmp_path / "uploads"
    get_session_factory.cache_clear()
    get_engine.cache_clear()


async def close_test_database() -> None:
    await get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()


def test_supported_image_formats_complete_ocr_correction_review_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_test_database(tmp_path)
    monkeypatch.setattr("app.modules.ocr.service.get_ocr_engine", lambda _="paddle": StaticOcrEngine())
    monkeypatch.setattr("app.modules.reviews.service.get_review_provider_registry", provider_registry)

    async def scenario() -> None:
        essay_ids: list[UUID] = []
        user_id: UUID | None = None
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                user_id = await authenticate(client)
                upload = await client.post(
                    "/api/essays",
                    files=[
                        ("images", ("camera.jpg", encode_image(".jpg"), "image/jpg")),
                        ("images", ("gallery.jpeg", encode_image(".jpg"), "image/jpeg")),
                        ("images", ("page-3.png", encode_image(".png"), "image/png")),
                        ("images", ("page-4.webp", encode_image(".webp"), "application/octet-stream")),
                    ],
                )
                assert upload.status_code == 201, upload.text
                essay_id = UUID(upload.json()["id"])
                essay_ids.append(essay_id)
                assert [source["mime_type"] for source in upload.json()["sources"]] == [
                    "image/jpeg",
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                ]

                ocr = await client.post(f"/api/essays/{essay_id}/ocr?engine=paddle")
                assert ocr.status_code == 201, ocr.text
                ocr_payload = ocr.json()
                assert ocr_payload["status"] == "completed"
                assert [page["page_number"] for page in ocr_payload["pages"]] == [1, 2, 3, 4]
                assert all(page["blocks"][0]["polygon_original"] for page in ocr_payload["pages"])

                correction = await client.get(f"/api/essays/{essay_id}/ocr/correction")
                assert correction.status_code == 200, correction.text
                first_block = correction.json()["pages"][0]["blocks"][0]
                saved = await client.put(
                    f"/api/essays/{essay_id}/ocr/correction",
                    json={
                        "blocks": [
                            {
                                "ocr_block_id": first_block["ocr_block_id"],
                                "corrected_text": f"{ESSAY_TEXT} The leaves rustled softly.",
                            }
                        ]
                    },
                )
                assert saved.status_code == 200, saved.text
                confirmed = await client.post(f"/api/essays/{essay_id}/ocr/correction/confirm")
                assert confirmed.status_code == 200, confirmed.text
                assert confirmed.json()["status"] == "confirmed"

                review = await client.post(
                    f"/api/essays/{essay_id}/reviews/batches",
                    json={"providers": ["deepseek", "qwen", "doubao"]},
                )
                assert review.status_code == 202, review.text
                batches = await client.get(f"/api/essays/{essay_id}/reviews/batches")
                assert batches.status_code == 200, batches.text
                result = batches.json()[0]
                assert result["text_source"] == "ocr_corrected"
                assert len(result["reviews"]) == 3
                assert result["final_evaluation"]["overall_score"] == 86
                assert result["final_evaluation"]["confidence"] is not None
                assert len(result["final_evaluation"]["dimension_scores"]) == 4

                report = await client.get(f"/api/essays/{essay_id}/reports/latest")
                assert report.status_code == 200
                assert report.json()["overall_score"] == 86
        finally:
            await cleanup_records(essay_ids, user_id)
            await close_test_database()

    asyncio.run(scenario())


def test_failed_image_recognition_can_retry_without_reuploading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_test_database(tmp_path)
    engine = FailOnceOcrEngine()
    monkeypatch.setattr("app.modules.ocr.service.get_ocr_engine", lambda _="paddle": engine)

    async def scenario() -> None:
        essay_ids: list[UUID] = []
        user_id: UUID | None = None
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                user_id = await authenticate(client)
                upload = await client.post(
                    "/api/essays",
                    files={"images": ("camera.jpg", encode_image(".jpg"), "image/jpeg")},
                )
                assert upload.status_code == 201, upload.text
                essay_id = UUID(upload.json()["id"])
                essay_ids.append(essay_id)

                failed = await client.post(f"/api/essays/{essay_id}/ocr")
                assert failed.status_code == 201, failed.text
                failed_payload = failed.json()
                assert failed_payload["status"] == "failed"
                assert "internal OCR adapter secret" not in (failed_payload["error_message"] or "")
                assert "重试" in failed_payload["pages"][0]["error_message"]

                retried = await client.post(f"/api/essays/{essay_id}/ocr")
                assert retried.status_code == 201, retried.text
                assert retried.json()["status"] == "completed"
                assert retried.json()["attempt_no"] == 2
                assert retried.json()["pages"][0]["blocks"]
        finally:
            await cleanup_records(essay_ids, user_id)
            await close_test_database()

    asyncio.run(scenario())


def test_direct_text_gets_report_and_empty_model_results_do_not_create_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_test_database(tmp_path)

    async def scenario() -> None:
        essay_ids: list[UUID] = []
        user_id: UUID | None = None
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                user_id = await authenticate(client)
                successful_upload = await client.post(
                    "/api/essays", data={"title": "Direct text", "original_text": ESSAY_TEXT}
                )
                assert successful_upload.status_code == 201, successful_upload.text
                successful_id = UUID(successful_upload.json()["id"])
                essay_ids.append(successful_id)
                history_before_review = await client.get("/api/essays")
                assert history_before_review.status_code == 200
                assert history_before_review.json()["items"] == []

                monkeypatch.setattr(
                    "app.modules.reviews.service.get_review_provider_registry", provider_registry
                )
                successful_review = await client.post(
                    f"/api/essays/{successful_id}/reviews/batches",
                    json={"providers": ["deepseek", "qwen", "doubao"]},
                )
                assert successful_review.status_code == 202, successful_review.text
                successful_batches = await client.get(f"/api/essays/{successful_id}/reviews/batches")
                assert successful_batches.status_code == 200, successful_batches.text
                successful_payload = successful_batches.json()[0]
                assert successful_payload["text_source"] == "direct_input"
                assert successful_payload["final_evaluation"]["overall_score"] == 86
                assert successful_payload["final_evaluation"]["summary"]
                assert successful_payload["reviews"][0]["annotations"]
                assert successful_payload["reviews"][0]["result"]["improvement_suggestions"]
                history_after_review = await client.get("/api/essays")
                assert [item["id"] for item in history_after_review.json()["items"]] == [
                    str(successful_id)
                ]

                failed_upload = await client.post(
                    "/api/essays", data={"title": "Unavailable models", "original_text": ESSAY_TEXT}
                )
                assert failed_upload.status_code == 201, failed_upload.text
                failed_id = UUID(failed_upload.json()["id"])
                essay_ids.append(failed_id)
                monkeypatch.setattr(
                    "app.modules.reviews.service.get_review_provider_registry",
                    lambda: provider_registry(configured=False),
                )
                failed_review = await client.post(
                    f"/api/essays/{failed_id}/reviews/batches",
                    json={"providers": ["deepseek", "qwen", "doubao"]},
                )
                assert failed_review.status_code == 202

                batches = await client.get(f"/api/essays/{failed_id}/reviews/batches")
                assert batches.status_code == 200
                assert batches.json()[0]["status"] == "failed"
                assert batches.json()[0]["final_evaluation"] is None
                latest = await client.get(f"/api/essays/{failed_id}/reports/latest")
                assert latest.status_code == 404

                # A new browser session starts with /auth/me. It removes only
                # unfinished tasks and compacts completed history without
                # making the final report unreadable.
                me = await client.get("/api/auth/me")
                assert me.status_code == 200, me.text
                assert (await client.get(f"/api/essays/{failed_id}")).status_code == 404
                compact_report = await client.get(
                    f"/api/essays/{successful_id}/reports/latest"
                )
                assert compact_report.status_code == 200, compact_report.text
                assert compact_report.json()["overall_score"] == 86

            async with get_session_factory()() as session:
                final_count = await session.scalar(
                    select(func.count(FinalEvaluation.id)).where(FinalEvaluation.essay_id == failed_id)
                )
                assert final_count == 0
                compact_model_review_count = await session.scalar(
                    select(func.count(ModelReview.id)).where(
                        ModelReview.essay_id == successful_id
                    )
                )
                compact_source_count = await session.scalar(
                    select(func.count(EssaySource.id)).where(
                        EssaySource.essay_id == successful_id
                    )
                )
                assert compact_model_review_count == 0
                assert compact_source_count == 0
        finally:
            await cleanup_records(essay_ids, user_id)
            await close_test_database()

    asyncio.run(scenario())
