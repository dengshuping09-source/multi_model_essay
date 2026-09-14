from __future__ import annotations

import asyncio
import os
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.models import Essay, EssayStatus, FinalEvaluation, ReviewStatus
from app.db.session import get_engine, get_session_factory
from app.main import app
from app.modules.materials.catalog import search_materials
from app.modules.materials.service import recommend_materials
from app.schemas.material import WritingMaterial
from tests.auth_helpers import authenticate_test_client, delete_test_user


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def test_material_search_and_explainable_recommendation_are_catalog_based() -> None:
    assert any(item.id == "sima-qian-shiji" for item in search_materials(query="坚持"))
    assert any(item.id == "tu-youyou-artemisinin" for item in search_materials(query="科研精神"))
    assert all("坚持" in item.themes for item in search_materials(theme="坚持"))
    assert [item.id for item in search_materials(category="科技")] == ["beidou-navigation"]
    recommendations = recommend_materials(
        search_materials(),
        topic="坚持让我成长",
        idea="面对挫折也不放弃，要把观点写得具体。",
        issue="论据展开不足，例子还不够具体。",
    )
    assert recommendations
    assert any("题目" in sources for _, _, sources in recommendations)
    assert any("当前反馈" in sources for _, _, sources in recommendations)
    assert all(material.source_kind in {"公共事实", "生活观察"} for material, _, _ in recommendations)
    assert any("论证角度" in reason for _, reason, sources in recommendations if "立意" in sources)


def test_material_details_are_curated_and_legacy_reference_field_is_optional() -> None:
    tested_ids = {
        "tu-youyou-artemisinin",
        "sima-qian-shiji",
        "beidou-navigation",
        "dunhuang-conservation",
        "barrier-free-community",
        "flood-relief-cooperation",
    }
    tested = [item for item in search_materials() if item.id in tested_ids]
    assert len(tested) == len(tested_ids)
    assert all(3 <= len(item.themes) <= 6 for item in tested)
    assert all(item.supports_claims and item.common_misuse and item.example_use for item in tested)
    assert all(item.reference_links for item in tested)
    assert all(
        reference.url.startswith("https://")
        for item in tested
        for reference in item.reference_links
    )
    assert search_materials(query="整理校园图书角")[0].reference_links == []

    legacy = WritingMaterial(
        id="legacy",
        title="旧素材",
        category="青春成长",
        source_kind="生活观察",
        background="旧数据只有原有字段。",
        core_facts=["事实清楚。"],
        themes=["成长"],
        supports_claims=["成长来自行动。"],
        how_to_use="联系自己的经历。",
        common_misuse="不要编造。",
        example_use="用自己的经历说明变化。",
        fact_check_note="请核对自己的经历。",
    )
    assert legacy.reference_links == []


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
def test_browse_search_filter_favorite_and_context_recommendations() -> None:
    settings.database_url = TEST_DATABASE_URL
    get_session_factory.cache_clear()
    get_engine.cache_clear()

    async def scenario() -> None:
        user_id: UUID | None = None
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                public_browse = await client.get("/api/materials/")
                assert public_browse.status_code == 200, public_browse.text
                assert public_browse.json()["total"] >= 8

                search = await client.get("/api/materials/", params={"query": "坚持"})
                assert search.status_code == 200
                assert any(item["id"] == "sima-qian-shiji" for item in search.json()["items"])

                category = await client.get("/api/materials/", params={"category": "科技"})
                assert category.status_code == 200
                assert [item["id"] for item in category.json()["items"]] == ["beidou-navigation"]

                theme = await client.get("/api/materials/", params={"theme": "坚持"})
                assert theme.status_code == 200
                assert theme.json()["items"]
                assert all("坚持" in item["themes"] for item in theme.json()["items"])

                detail = await client.get("/api/materials/dunhuang-conservation")
                assert detail.status_code == 200
                assert detail.json()["common_misuse"]
                assert detail.json()["reference_links"][0]["url"].startswith("https://")
                assert (await client.get("/api/materials/", params={"favorites_only": "true"})).status_code == 401

                user_id = await authenticate_test_client(client)
                favorite = await client.put("/api/materials/sima-qian-shiji/favorite")
                assert favorite.status_code == 200
                assert favorite.json()["is_favorited"] is True
                favorites = await client.get("/api/materials/", params={"favorites_only": "true"})
                assert favorites.status_code == 200
                assert [item["id"] for item in favorites.json()["items"]] == ["sima-qian-shiji"]

                viewed_ids = [
                    "tu-youyou-artemisinin",
                    "sima-qian-shiji",
                    "beidou-navigation",
                    "dunhuang-conservation",
                    "barrier-free-community",
                ]
                for material_id in viewed_ids:
                    viewed = await client.put(f"/api/materials/{material_id}/recent-view")
                    assert viewed.status_code == 200, viewed.text
                    assert viewed.json()["material"]["id"] == material_id
                recent = await client.get("/api/materials/recent")
                assert recent.status_code == 200, recent.text
                assert [item["material"]["id"] for item in recent.json()["items"]] == list(reversed(viewed_ids))
                repeated = await client.put("/api/materials/sima-qian-shiji/recent-view")
                assert repeated.status_code == 200
                recent_after_repeat = await client.get("/api/materials/recent")
                recent_ids = [item["material"]["id"] for item in recent_after_repeat.json()["items"]]
                assert recent_ids[0] == "sima-qian-shiji"
                assert len(recent_ids) == len(set(recent_ids)) == len(viewed_ids)

                # Personalisation only starts after repeated, formal evaluation evidence.
                async with get_session_factory()() as session:
                    for index in range(3):
                        essay = Essay(
                            author_id=user_id,
                            title=f"素材推荐历史样本 {index + 1}",
                            original_text="这是一篇用于验证素材推荐历史依据的正式作文。",
                            full_score=100,
                            status=EssayStatus.EVALUATED,
                        )
                        session.add(essay)
                        await session.flush()
                        session.add(
                            FinalEvaluation(
                                essay_id=essay.id,
                                version=1,
                                status=ReviewStatus.COMPLETED,
                                overall_score=78 + index,
                                dimension_scores=[],
                                aggregation_config={
                                    "learning_feedback": {
                                        "priority_issues": [
                                            {
                                                "category": "content",
                                                "issue_type": "development",
                                                "suggestion": "补充分析，解释材料为什么能够证明观点。",
                                            }
                                        ]
                                    }
                                },
                            )
                        )
                    await session.commit()

                recommended = await client.get(
                    "/api/materials/recommendations",
                    params={"topic": "坚持让我成长", "idea": "在困难中不放弃", "issue": "论据展开不足"},
                )
                assert recommended.status_code == 200, recommended.text
                payload = recommended.json()
                assert payload["context_available"] is True
                assert payload["items"]
                assert any("题目" in item["sources"] for item in payload["items"])
                assert any("当前反馈" in item["sources"] for item in payload["items"])
                assert any(item["material"]["is_favorited"] for item in payload["items"])
                assert payload["personalized"] is True
                assert any("历史弱项" in item["sources"] for item in payload["items"])

                unfavorite = await client.delete("/api/materials/sima-qian-shiji/favorite")
                assert unfavorite.status_code == 200
                assert unfavorite.json()["is_favorited"] is False
                cleared = await client.delete("/api/materials/recent")
                assert cleared.status_code == 200
                assert (await client.get("/api/materials/recent")).json()["items"] == []
        finally:
            await delete_test_user(user_id)
            await get_engine().dispose()
            get_session_factory.cache_clear()
            get_engine.cache_clear()

    asyncio.run(scenario())
