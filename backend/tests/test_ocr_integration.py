import asyncio
import os
from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Essay, OcrBlock, OcrCorrection, OcrPageResult, OcrRun
from app.db.session import get_engine, get_session_factory
from app.main import app
from app.modules.ocr.engine import RecognizedRegion
from tests.auth_helpers import authenticate_test_client, delete_test_user

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


class FakeOcrEngine:
    engine_name = "test-ocr"
    detection_model = "test-det"
    recognition_model = "test-rec"

    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, _: Path) -> list[RecognizedRegion]:
        responses = [
            [
                RecognizedRegion("今天的天空很蓝。", [[40, 80], [300, 80], [300, 112], [40, 112]], 0.94),
                RecognizedRegion("我和同学去公园。", [[42, 130], [320, 130], [320, 163], [42, 163]], 0.91),
            ],
            [
                RecognizedRegion("我们度过了快乐的一天。", [[36, 92], [380, 92], [380, 126], [36, 126]], 0.89),
            ],
        ]
        response = responses[self.calls]
        self.calls += 1
        return response


class LowConfidenceAndEmptyEngine:
    engine_name = "test-ocr"
    detection_model = "test-det"
    recognition_model = "test-rec"

    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, _: Path) -> list[RecognizedRegion]:
        self.calls += 1
        if self.calls == 1:
            return [
                RecognizedRegion("需要人工核对的文字", [[40, 80], [300, 80], [300, 112], [40, 112]], 0.32)
            ]
        return []


class StaticOcrEngine:
    def __init__(self, engine_name: str, text: str, confidence: float | None) -> None:
        self.engine_name = engine_name
        self.detection_model = f"{engine_name}-det"
        self.recognition_model = f"{engine_name}-rec"
        self.text = text
        self.confidence = confidence

    def recognize(self, _: Path) -> list[RecognizedRegion]:
        return [
            RecognizedRegion(
                self.text,
                [[40, 80], [300, 80], [300, 112], [40, 112]],
                self.confidence,
            )
        ]


def document_image() -> np.ndarray:
    image = np.full((800, 600, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (25, 20), (575, 780), (210, 210, 210), 3)
    for y in range(80, 740, 38):
        cv2.line(image, (65, y), (535, y), (55, 55, 55), 3)
    return image


def encode(image: np.ndarray, extension: str = ".png") -> bytes:
    ok, payload = cv2.imencode(extension, image)
    assert ok
    return payload.tobytes()


def test_multi_page_ocr_api_persists_page_order_blocks_and_coordinates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.database_url = TEST_DATABASE_URL
    settings.upload_dir = tmp_path / "uploads"
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    engine = FakeOcrEngine()
    monkeypatch.setattr("app.modules.ocr.service.get_ocr_engine", lambda _="paddle": engine)

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                upload = await client.post(
                    "/api/essays",
                    files=[
                        ("images", ("page-1.png", encode(document_image()), "image/png")),
                        ("images", ("page-2.png", encode(document_image()), "image/png")),
                    ],
                )
                assert upload.status_code == 201
                essay_id = UUID(upload.json()["id"])

                response = await client.post(f"/api/essays/{essay_id}/ocr")
                assert response.status_code == 201
                payload = response.json()
                assert payload["status"] == "completed"
                assert payload["combined_text"] == (
                    "今天的天空很蓝。\n我和同学去公园。\n\n我们度过了快乐的一天。"
                )
                assert [page["page_number"] for page in payload["pages"]] == [1, 2]
                assert [page["block_count"] for page in payload["pages"]] == [2, 1]
                assert payload["pages"][0]["blocks"][0]["reading_order"] == 0
                assert payload["pages"][0]["blocks"][0]["polygon_original"] is not None

                fetched = await client.get(f"/api/essays/{essay_id}/ocr")
                assert fetched.status_code == 200
                assert fetched.json()["id"] == payload["id"]

            async with get_session_factory()() as session:
                stored_run = await session.scalar(
                    select(OcrRun)
                    .where(OcrRun.essay_id == essay_id)
                    .options(selectinload(OcrRun.pages).selectinload(OcrPageResult.blocks))
                )
                assert stored_run is not None
                assert stored_run.total_blocks == 3
                assert len(stored_run.pages) == 2
                assert sum(len(page.blocks) for page in stored_run.pages) == 3
                assert all(block.polygon_original for page in stored_run.pages for block in page.blocks)
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


def test_low_confidence_and_empty_pages_are_not_reported_as_normal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.database_url = TEST_DATABASE_URL
    settings.upload_dir = tmp_path / "uploads"
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    engine = LowConfidenceAndEmptyEngine()
    monkeypatch.setattr("app.modules.ocr.service.get_ocr_engine", lambda _="paddle": engine)

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                image = encode(document_image())
                upload = await client.post(
                    "/api/essays",
                    files=[
                        ("images", ("low.png", image, "image/png")),
                        ("images", ("empty.png", image, "image/png")),
                    ],
                )
                essay_id = UUID(upload.json()["id"])
                response = await client.post(f"/api/essays/{essay_id}/ocr")
                payload = response.json()
                assert payload["status"] == "partial"
                assert [page["status"] for page in payload["pages"]] == [
                    "low_confidence",
                    "empty",
                ]
                assert payload["pages"][0]["warnings"]
                assert payload["pages"][1]["warnings"]
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


def test_paddle_and_baidu_runs_are_saved_independently_for_one_essay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.database_url = TEST_DATABASE_URL
    settings.upload_dir = tmp_path / "uploads"
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    engines = {
        "paddle": StaticOcrEngine("PaddleOCR test", "Paddle result", 0.92),
        "baidu": StaticOcrEngine("Baidu OCR test", "Baidu result", None),
    }
    monkeypatch.setattr(
        "app.modules.ocr.service.get_ocr_engine", lambda engine_key="paddle": engines[engine_key]
    )

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                upload = await client.post(
                    "/api/essays",
                    files=[("images", ("page.png", encode(document_image()), "image/png"))],
                )
                essay_id = UUID(upload.json()["id"])
                paddle = await client.post(f"/api/essays/{essay_id}/ocr?engine=paddle")
                baidu = await client.post(f"/api/essays/{essay_id}/ocr?engine=baidu")
                assert paddle.status_code == 201
                assert baidu.status_code == 201
                assert paddle.json()["engine_key"] == "paddle"
                assert baidu.json()["engine_key"] == "baidu"
                assert paddle.json()["combined_text"] == "Paddle result"
                assert baidu.json()["combined_text"] == "Baidu result"
                assert baidu.json()["pages"][0]["blocks"][0]["confidence"] is None

                paddle_latest = await client.get(f"/api/essays/{essay_id}/ocr?engine=paddle")
                baidu_latest = await client.get(f"/api/essays/{essay_id}/ocr?engine=baidu")
                assert paddle_latest.json()["id"] == paddle.json()["id"]
                assert baidu_latest.json()["id"] == baidu.json()["id"]

            async with get_session_factory()() as session:
                runs = list(
                    (
                        await session.scalars(
                            select(OcrRun)
                            .where(OcrRun.essay_id == essay_id)
                            .options(selectinload(OcrRun.pages).selectinload(OcrPageResult.blocks))
                        )
                    ).all()
                )
                assert {run.engine_key for run in runs} == {"paddle", "baidu"}
                assert {page.blocks[0].text for run in runs for page in run.pages} == {
                    "Paddle result",
                    "Baidu result",
                }
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


def test_single_page_ocr_correction_returns_original_coordinate_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.database_url = TEST_DATABASE_URL
    settings.upload_dir = tmp_path / "uploads"
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setattr("app.modules.ocr.service.get_ocr_engine", lambda _="paddle": FakeOcrEngine())

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                upload = await client.post(
                    "/api/essays",
                    files=[("images", ("single.png", encode(document_image()), "image/png"))],
                )
                essay_id = UUID(upload.json()["id"])
                assert (await client.post(f"/api/essays/{essay_id}/ocr")).status_code == 201

                correction = await client.get(f"/api/essays/{essay_id}/ocr/correction")
                assert correction.status_code == 200
                payload = correction.json()
                assert len(payload["pages"]) == 1
                block = payload["pages"][0]["blocks"][0]
                assert block["corrected_text"] == block["original_text"]
                assert block["polygon_original"] is not None
                assert not block["is_modified"]
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


def test_ocr_correction_preserves_original_text_and_confirms_multi_page_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.database_url = TEST_DATABASE_URL
    settings.upload_dir = tmp_path / "uploads"
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    engine = FakeOcrEngine()
    monkeypatch.setattr("app.modules.ocr.service.get_ocr_engine", lambda _="paddle": engine)

    async def scenario() -> None:
        essay_id: UUID | None = None
        user_id: UUID | None = None
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                image = encode(document_image())
                upload = await client.post(
                    "/api/essays",
                    files=[
                        ("images", ("page-1.png", image, "image/png")),
                        ("images", ("page-2.png", image, "image/png")),
                    ],
                )
                essay_id = UUID(upload.json()["id"])
                assert (await client.post(f"/api/essays/{essay_id}/ocr")).status_code == 201

                initial = await client.get(f"/api/essays/{essay_id}/ocr/correction")
                assert initial.status_code == 200
                initial_payload = initial.json()
                assert [page["page_number"] for page in initial_payload["pages"]] == [1, 2]
                first_block = initial_payload["pages"][0]["blocks"][0]
                assert first_block["corrected_text"] == "今天的天空很蓝。"
                assert not first_block["is_modified"]

                saved = await client.put(
                    f"/api/essays/{essay_id}/ocr/correction",
                    json={
                        "blocks": [
                            {
                                "ocr_block_id": first_block["ocr_block_id"],
                                "corrected_text": "今天的天空很蓝，很清澈。",
                            }
                        ]
                    },
                )
                assert saved.status_code == 200
                saved_payload = saved.json()
                assert saved_payload["status"] == "draft"
                assert saved_payload["pages"][0]["blocks"][0]["is_modified"]
                assert "很清澈" in saved_payload["corrected_text"]

                ocr_payload = (await client.get(f"/api/essays/{essay_id}/ocr")).json()
                assert ocr_payload["pages"][0]["blocks"][0]["text"] == "今天的天空很蓝。"

                confirmed = await client.post(f"/api/essays/{essay_id}/ocr/correction/confirm")
                assert confirmed.status_code == 200
                assert confirmed.json()["status"] == "confirmed"
                assert confirmed.json()["confirmed_at"] is not None

            async with get_session_factory()() as session:
                original_block = await session.scalar(
                    select(OcrBlock).where(OcrBlock.id == UUID(first_block["ocr_block_id"]))
                )
                correction = await session.scalar(
                    select(OcrCorrection).where(OcrCorrection.essay_id == essay_id)
                )
                assert original_block is not None
                assert original_block.text == "今天的天空很蓝。"
                assert correction is not None
                assert "很清澈" in (correction.corrected_text or "")
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
