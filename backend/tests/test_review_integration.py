import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Essay, ModelReview, OcrCorrection, OcrCorrectionStatus, OcrRun, OcrRunStatus, ReviewStatus
from app.db.session import get_engine, get_session_factory
from app.main import app
from app.modules.reviews.contracts import (
    DimensionScore,
    EssayReviewOutput,
    EvidenceItem,
    ImprovementSuggestion,
    ReviewAnnotation,
)
from app.modules.reviews.deepseek import (
    DeepSeekResponseFormatError,
    DeepSeekTimeoutError,
    ProviderReviewResult,
)
from tests.auth_helpers import authenticate_test_client, delete_test_user

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)

ESSAY_TEXT = "Rain cleared the street. I went home and wrote about the quiet evening."


def review_output() -> EssayReviewOutput:
    return EssayReviewOutput(
        overall_score=86,
        summary="The essay has a clear scene and a complete ending.",
        dimension_scores=[
            DimensionScore(
                dimension="content_and_ideas",
                score=22,
                max_score=25,
                rationale="The scene is focused.",
                evidence=[EvidenceItem(quote="Rain cleared the street", rationale="Sets the scene.")],
            ),
            DimensionScore(
                dimension="structure_and_coherence",
                score=22,
                max_score=25,
                rationale="Events follow a clear order.",
                evidence=[EvidenceItem(quote="I went home", rationale="Moves the narrative forward.")],
            ),
            DimensionScore(
                dimension="language_and_expression",
                score=21,
                max_score=25,
                rationale="The wording is understandable but could be more vivid.",
                evidence=[EvidenceItem(quote="quiet evening", rationale="A useful image that could be expanded.")],
            ),
            DimensionScore(
                dimension="writing_conventions",
                score=21,
                max_score=25,
                rationale="Sentences and punctuation are consistent.",
                evidence=[EvidenceItem(quote="wrote about", rationale="The clause is complete.")],
            ),
        ],
        annotations=[
            ReviewAnnotation(
                category="expression",
                severity="medium",
                quote="quiet evening",
                comment="The ending is a little general.",
                suggestion="Add one concrete sensory detail.",
            )
        ],
        improvement_suggestions=[
            ImprovementSuggestion(
                priority="medium",
                category="expression",
                suggestion="Use one sensory detail at the end.",
                example_revision="The wet street reflected the last light.",
            )
        ],
    )


class FakeDeepSeekClient:
    async def review(self, _: str) -> ProviderReviewResult:
        return ProviderReviewResult(
            output=review_output(),
            provider_response_id="test-review-id",
            model_name="deepseek-chat-test-version",
            usage={"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        )


class TimeoutDeepSeekClient:
    async def review(self, _: str) -> ProviderReviewResult:
        raise DeepSeekTimeoutError("DeepSeek review request timed out")


class InvalidFormatDeepSeekClient:
    async def review(self, _: str) -> ProviderReviewResult:
        raise DeepSeekResponseFormatError("DeepSeek returned a review with an invalid structure")


def test_deepseek_review_persists_structured_direct_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.database_url = TEST_DATABASE_URL
    settings.upload_dir = tmp_path / "uploads"
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setattr("app.modules.reviews.service.get_deepseek_client", lambda: FakeDeepSeekClient())

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                upload = await client.post("/api/essays", data={"original_text": ESSAY_TEXT})
                assert upload.status_code == 201
                essay_id = UUID(upload.json()["id"])

                response = await client.post(f"/api/essays/{essay_id}/reviews/deepseek")
                assert response.status_code == 201
                payload = response.json()
                assert payload["status"] == "completed"
                assert payload["text_source"] == "direct_input"
                assert payload["evaluated_text"] == ESSAY_TEXT
                assert payload["overall_score"] == 86
                assert len(payload["result"]["dimension_scores"]) == 4
                assert payload["result"]["annotations"][0]["quote"] == "quiet evening"

                listed = await client.get(f"/api/essays/{essay_id}/reviews")
                assert listed.status_code == 200
                assert len(listed.json()["items"]) == 1

            async with get_session_factory()() as session:
                review = await session.scalar(
                    select(ModelReview)
                    .where(ModelReview.essay_id == essay_id)
                    .options(
                        selectinload(ModelReview.annotations),
                        selectinload(ModelReview.score_evidence),
                    )
                )
                assert review is not None
                assert review.status is ReviewStatus.COMPLETED
                assert review.evaluated_text == ESSAY_TEXT
                assert review.model_version == "deepseek-chat-test-version"
                assert len(review.annotations) == 1
                assert review.annotations[0].evidence_text == "quiet evening"
                assert len(review.score_evidence) == 4
                assert review.raw_response is not None
                assert review.raw_response["usage"]["total_tokens"] == 300
        finally:
            if essay_id is not None:
                async with get_session_factory()() as session:
                    await session.execute(delete(Essay).where(Essay.id == essay_id))
                    await session.commit()
            await delete_test_user(user_id)
            await get_engine().dispose()
            get_session_factory.cache_clear()
            get_engine.cache_clear()

    asyncio.run(scenario())


def test_confirmed_ocr_text_is_selected_before_direct_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.database_url = TEST_DATABASE_URL
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setattr("app.modules.reviews.service.get_deepseek_client", lambda: FakeDeepSeekClient())

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                async with get_session_factory()() as session:
                    essay = Essay(original_text=ESSAY_TEXT, author_id=user_id)
                    session.add(essay)
                    await session.flush()
                    essay_id = essay.id
                    run = OcrRun(
                        essay_id=essay.id,
                        attempt_no=1,
                        status=OcrRunStatus.COMPLETED,
                        engine_name="test",
                        detection_model="test",
                        recognition_model="test",
                        total_blocks=0,
                        completed_at=datetime.now(timezone.utc),
                    )
                    session.add(run)
                    await session.flush()
                    corrected_text = "Corrected OCR essay text."
                    session.add(
                        OcrCorrection(
                            essay_id=essay.id,
                            ocr_run_id=run.id,
                            status=OcrCorrectionStatus.CONFIRMED,
                            corrected_text=corrected_text,
                            confirmed_at=datetime.now(timezone.utc),
                        )
                    )
                    await session.commit()
                response = await client.post(f"/api/essays/{essay_id}/reviews/deepseek")
                assert response.status_code == 201
                assert response.json()["text_source"] == "ocr_corrected"
                assert response.json()["evaluated_text"] == "Corrected OCR essay text."
        finally:
            if essay_id is not None:
                async with get_session_factory()() as session:
                    await session.execute(delete(Essay).where(Essay.id == essay_id))
                    await session.commit()
            await delete_test_user(user_id)
            await get_engine().dispose()
            get_session_factory.cache_clear()
            get_engine.cache_clear()

    asyncio.run(scenario())


def test_deepseek_timeout_is_saved_as_a_failed_review(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.database_url = TEST_DATABASE_URL
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setattr("app.modules.reviews.service.get_deepseek_client", lambda: TimeoutDeepSeekClient())

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                async with get_session_factory()() as session:
                    essay = Essay(original_text=ESSAY_TEXT, author_id=user_id)
                    session.add(essay)
                    await session.commit()
                    essay_id = essay.id
                response = await client.post(f"/api/essays/{essay_id}/reviews/deepseek")
                assert response.status_code == 504
                listed = await client.get(f"/api/essays/{essay_id}/reviews")
                item = listed.json()["items"][0]
                assert item["status"] == "failed"
                assert item["error_message"] == "这一路评审暂时未能完成，可稍后重试"
        finally:
            if essay_id is not None:
                async with get_session_factory()() as session:
                    await session.execute(delete(Essay).where(Essay.id == essay_id))
                    await session.commit()
            await delete_test_user(user_id)
            await get_engine().dispose()
            get_session_factory.cache_clear()
            get_engine.cache_clear()

    asyncio.run(scenario())


def test_invalid_deepseek_format_is_saved_as_a_failed_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.database_url = TEST_DATABASE_URL
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setattr(
        "app.modules.reviews.service.get_deepseek_client", lambda: InvalidFormatDeepSeekClient()
    )

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                async with get_session_factory()() as session:
                    essay = Essay(original_text=ESSAY_TEXT, author_id=user_id)
                    session.add(essay)
                    await session.commit()
                    essay_id = essay.id
                response = await client.post(f"/api/essays/{essay_id}/reviews/deepseek")
                assert response.status_code == 502
                listed = await client.get(f"/api/essays/{essay_id}/reviews")
                item = listed.json()["items"][0]
                assert item["status"] == "failed"
                assert item["error_message"] == "这一路评审暂时未能完成，可稍后重试"
        finally:
            if essay_id is not None:
                async with get_session_factory()() as session:
                    await session.execute(delete(Essay).where(Essay.id == essay_id))
                    await session.commit()
            await delete_test_user(user_id)
            await get_engine().dispose()
            get_session_factory.cache_clear()
            get_engine.cache_clear()

    asyncio.run(scenario())
