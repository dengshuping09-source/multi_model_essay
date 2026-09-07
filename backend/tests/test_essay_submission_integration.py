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
from app.db.models import Essay, EssaySource, SourceType
from app.db.session import get_engine, get_session_factory
from app.main import app
from tests.auth_helpers import authenticate_test_client, delete_test_user

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


def document_image() -> np.ndarray:
    image = np.full((800, 600, 3), 245, dtype=np.uint8)
    for y in range(80, 740, 38):
        cv2.line(image, (70, y), (530, y), (55, 55, 55), 3)
    return image


def perspective_document() -> np.ndarray:
    document = document_image()
    canvas = np.full((920, 760, 3), 55, dtype=np.uint8)
    source = np.float32([[0, 0], [599, 0], [599, 799], [0, 799]])
    destination = np.float32([[105, 55], [680, 100], [640, 860], [65, 810]])
    transform = cv2.getPerspectiveTransform(source, destination)
    warped = cv2.warpPerspective(document, transform, (760, 920))
    mask = cv2.warpPerspective(np.full(document.shape[:2], 255, dtype=np.uint8), transform, (760, 920))
    canvas[mask > 0] = warped[mask > 0]
    return canvas


def image_bytes(image: np.ndarray, extension: str) -> bytes:
    success, encoded = cv2.imencode(extension, image)
    assert success
    return encoded.tobytes()


def test_text_single_image_and_multi_image_submissions(tmp_path: Path) -> None:
    settings.database_url = TEST_DATABASE_URL
    settings.upload_dir = tmp_path / "uploads"
    get_session_factory.cache_clear()
    get_engine.cache_clear()

    async def run_scenarios() -> None:
        essay_ids: list[UUID] = []
        user_id: UUID | None = None
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            user_id = await authenticate_test_client(client)
            text_response = await client.post(
                "/api/essays",
                data={"title": "文字作文", "original_text": "这是一篇通过粘贴提交的作文。"},
            )
            assert text_response.status_code == 201
            text_payload = text_response.json()
            essay_ids.append(UUID(text_payload["id"]))
            assert text_payload["root_essay_id"] == text_payload["id"]
            assert text_payload["parent_essay_id"] is None
            assert text_payload["version_no"] == 1
            assert [source["source_type"] for source in text_payload["sources"]] == [
                "text_input"
            ]

            revision_response = await client.post(
                "/api/essays",
                data={
                    "title": "文字作文（修改稿）",
                    "original_text": "这是一篇经过修改后再次提交的作文。",
                    "parent_essay_id": text_payload["id"],
                },
            )
            assert revision_response.status_code == 201
            revision_payload = revision_response.json()
            essay_ids.append(UUID(revision_payload["id"]))
            assert revision_payload["root_essay_id"] == text_payload["id"]
            assert revision_payload["parent_essay_id"] == text_payload["id"]
            assert revision_payload["version_no"] == 2

            version_history = await client.get(f"/api/essays/{revision_payload['id']}/versions")
            assert version_history.status_code == 200
            version_payload = version_history.json()
            assert version_payload["root_essay_id"] == text_payload["id"]
            # Draft and ready rows are server-side session tasks, not history.
            assert version_payload["items"] == []
            history = await client.get("/api/essays")
            assert history.status_code == 200
            assert history.json()["items"] == []

            jpeg = image_bytes(document_image(), ".jpg")
            single_response = await client.post(
                "/api/essays",
                data={"title": "单图作文"},
                files={"images": ("page-one.jpeg", jpeg, "image/jpg")},
            )
            assert single_response.status_code == 201
            single_payload = single_response.json()
            essay_ids.append(UUID(single_payload["id"]))
            assert single_payload["sources"][0]["image_width"] == 600
            assert single_payload["sources"][0]["image_height"] == 800
            assert single_payload["sources"][0]["quality"]["status"] == "good"
            assert not single_payload["sources"][0]["quality"]["processed_available"]

            png = image_bytes(document_image(), ".png")
            webp = image_bytes(perspective_document(), ".webp")
            multi_response = await client.post(
                "/api/essays",
                files=[
                    ("images", ("first-page.png", png, "image/png")),
                    ("images", ("second-page.webp", webp, "application/octet-stream")),
                ],
            )
            assert multi_response.status_code == 201
            multi_payload = multi_response.json()
            essay_ids.append(UUID(multi_payload["id"]))
            assert [source["page_number"] for source in multi_payload["sources"]] == [1, 2]
            assert [source["mime_type"] for source in multi_payload["sources"]] == [
                "image/png",
                "image/webp",
            ]
            assert multi_payload["sources"][1]["quality"]["status"] == "improvable"
            assert multi_payload["sources"][1]["quality"]["processed_available"]
            assert "页面检测与透视矫正" in multi_payload["sources"][1]["quality"][
                "applied_operations"
            ]

            original_preview = await client.get(
                f"/api/essays/sources/{multi_payload['sources'][0]['id']}/images/original"
            )
            processed_preview = await client.get(
                f"/api/essays/sources/{multi_payload['sources'][1]['id']}/images/processed"
            )
            assert original_preview.status_code == 200
            assert original_preview.content == png
            assert processed_preview.status_code == 200
            assert processed_preview.headers["content-type"].startswith("image/png")

            invalid_response = await client.post(
                "/api/essays",
                files={"images": ("fake.jpg", b"not an image", "image/jpeg")},
            )
            assert invalid_response.status_code == 422

        async with get_session_factory()() as session:
            result = await session.scalars(
                select(Essay)
                .where(Essay.id.in_(essay_ids))
                .options(
                    selectinload(Essay.sources).selectinload(EssaySource.quality_analysis)
                )
            )
            essays = {essay.title: essay for essay in result.unique().all()}

            assert essays["文字作文"].original_text == "这是一篇通过粘贴提交的作文。"
            assert essays["文字作文"].sources[0].source_type is SourceType.TEXT_INPUT

            single_source = essays["单图作文"].sources[0]
            assert single_source.file_name == "page-one.jpeg"
            assert single_source.file_size_bytes == len(jpeg)
            assert (settings.upload_dir / single_source.storage_key).is_file()
            assert single_source.quality_analysis.quality_score == 100

            multi_essay = next(essay for essay in essays.values() if essay.title is None)
            ordered_sources = sorted(multi_essay.sources, key=lambda source: source.page_number or 0)
            assert [source.file_name for source in ordered_sources] == [
                "first-page.png",
                "second-page.webp",
            ]
            assert all((settings.upload_dir / source.storage_key).is_file() for source in ordered_sources)
            assert ordered_sources[1].quality_analysis.processed_storage_key
            assert (
                settings.upload_dir
                / ordered_sources[1].quality_analysis.processed_storage_key
            ).is_file()

            await session.execute(delete(Essay).where(Essay.id.in_(essay_ids)))
            await session.commit()

        await delete_test_user(user_id)

        await get_engine().dispose()
        get_session_factory.cache_clear()
        get_engine.cache_clear()

    asyncio.run(run_scenarios())
