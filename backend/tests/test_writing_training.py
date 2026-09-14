from __future__ import annotations

import asyncio
import os
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import Essay, EssayStatus, FinalEvaluation, ReviewStatus, WritingTrainingSession
from app.db.session import get_engine, get_session_factory
from app.main import app
from app.modules.training.service import GeneratedMicroTrainingFeedback, GeneratedTrainingFeedback
from app.schemas.training import MicroTrainingFeedback, TopicTrainingFeedback
from tests.auth_helpers import authenticate_test_client, delete_test_user


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def feedback(priority_issue: str = "中心还可以更具体。") -> TopicTrainingFeedback:
    return TopicTrainingFeedback(
        topic_understanding="mostly_accurate",
        idea_clarity="developing",
        off_topic_risk="low",
        structure_status="mostly_focused",
        missing_constraints=["还没有说明如何体现成长过程"],
        strengths=["抓住了题目中的成长关键词"],
        priority_issue=priority_issue,
        guidance=["想一想哪件具体事情最能表现这一变化"],
        next_step="先把中心改成包含具体事件和感受的一句话。",
    )


def micro_feedback() -> MicroTrainingFeedback:
    return MicroTrainingFeedback(
        achievement="met",
        strengths=["能够从具体动作进入，没有先空讲道理"],
        priority_issue="结尾还可以更明确地回应题目中的“没有退缩”。",
        suggestions=["补一句当时的选择或感受，让开头方向更清楚。"],
        recommend_retry=True,
        next_step="修改后再读一遍，检查开头是否自然引出了主要事件。",
    )


def test_issue_mapping_uses_structured_feedback_instead_of_exact_text() -> None:
    from app.api.routes.training import _recommended_exercise

    assert _recommended_exercise(
        {"category": "structure", "issue_type": "coherence", "label": "段落衔接不够自然"}
    ) == "paragraph_transition"
    assert _recommended_exercise(
        {"category": "content", "issue_type": "development", "label": "论据展开不足"}
    ) == "evidence_development"
    assert _recommended_exercise(
        {"category": "language", "issue_type": "wording", "label": "用词重复"}
    ) == "sentence_revision"


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
def test_topic_training_is_revisable_and_separate_from_essay_history(monkeypatch) -> None:
    from app.api.routes import training as training_routes
    from app.core.config import settings

    settings.database_url = TEST_DATABASE_URL
    get_session_factory.cache_clear()
    get_engine.cache_clear()

    calls = 0

    async def fake_generation(_):
        nonlocal calls
        calls += 1
        return GeneratedTrainingFeedback(
            feedback("第二次表达已经更清楚。" if calls > 1 else "中心还可以更具体。"),
            "test-provider",
            "test-model",
        )

    monkeypatch.setattr(training_routes, "generate_topic_training_feedback", fake_generation)

    async def scenario() -> None:
        user_id: UUID | None = None
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                submission = {
                    "topic_prompt": "以成长为题写一篇记叙文。",
                    "requirement_notes": "关键词是成长，要写具体事件。",
                    "central_idea": "写自己学会坚持。",
                    "outline": "遇到困难，继续练习，最后完成目标。",
                }
                created = await client.post("/api/training/topic-analysis", json=submission)
                assert created.status_code == 201, created.text
                training_id = created.json()["id"]
                assert created.json()["status"] == "completed"
                assert created.json()["attempt_count"] == 1

                revised_submission = {
                    **submission,
                    "central_idea": "通过坚持完成长跑，表达遇到困难也不放弃。",
                }
                revised = await client.put(
                    f"/api/training/topic-analysis/{training_id}", json=revised_submission
                )
                assert revised.status_code == 200, revised.text
                assert revised.json()["attempt_count"] == 2
                assert revised.json()["feedback"]["priority_issue"] == "第二次表达已经更清楚。"

                history = await client.get("/api/training/topic-analysis")
                assert history.status_code == 200
                assert [item["id"] for item in history.json()["items"]] == [training_id]
                essay_history = await client.get("/api/essays")
                assert essay_history.status_code == 200
                assert essay_history.json()["items"] == []

                async with get_session_factory()() as session:
                    record = await session.scalar(
                        select(WritingTrainingSession).where(
                            WritingTrainingSession.id == UUID(training_id)
                        )
                    )
                    assert record is not None
                    assert record.training_type == "topic_and_idea"
                    assert record.provider_key == "test-provider"
        finally:
            await delete_test_user(user_id)
            await get_engine().dispose()
            get_session_factory.cache_clear()
            get_engine.cache_clear()

    asyncio.run(scenario())


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
def test_micro_training_uses_one_feedback_call_and_stays_out_of_essay_history(monkeypatch) -> None:
    from app.api.routes import training as training_routes
    from app.core.config import settings

    settings.database_url = TEST_DATABASE_URL
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    calls = 0

    async def fake_generation(_task, _answer):
        nonlocal calls
        calls += 1
        return GeneratedMicroTrainingFeedback(micro_feedback(), "test-provider", "test-model")

    monkeypatch.setattr(training_routes, "generate_micro_training_feedback", fake_generation)

    async def scenario() -> None:
        user_id: UUID | None = None
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                recommendations = await client.get("/api/training/recommendations")
                assert recommendations.status_code == 200, recommendations.text
                assert recommendations.json()["personalized"] is False
                assert all(not item["personalized"] for item in recommendations.json()["items"])

                task = await client.get("/api/training/micro-exercises/opening")
                assert task.status_code == 200, task.text
                task_payload = task.json()
                result = await client.post(
                    "/api/training/micro-exercises",
                    json={
                        "task_id": task_payload["task_id"],
                        "response_text": "雨点打在窗上，我握着报名表站在门口，手心已经沁出了汗。想到昨天因为害怕而退缩，我深吸一口气，听见里面传来同学练习演讲的声音，终于推开了教室的门。这一次，我不想再把机会留给胆怯。",
                    },
                )
                assert result.status_code == 201, result.text
                assert result.json()["feedback"]["achievement"] == "met"
                assert calls == 1

                essay_history = await client.get("/api/essays")
                assert essay_history.status_code == 200
                assert essay_history.json()["items"] == []

                async with get_session_factory()() as session:
                    record = await session.scalar(
                        select(WritingTrainingSession).where(
                            WritingTrainingSession.id == UUID(result.json()["id"])
                        )
                    )
                    assert record is not None
                    assert record.training_type == "micro:opening"
                    assert record.provider_key == "test-provider"
        finally:
            await delete_test_user(user_id)
            await get_engine().dispose()
            get_session_factory.cache_clear()
            get_engine.cache_clear()

    asyncio.run(scenario())


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
def test_recommendations_require_repeated_evidence_across_formal_works() -> None:
    from app.core.config import settings

    settings.database_url = TEST_DATABASE_URL
    get_session_factory.cache_clear()
    get_engine.cache_clear()

    async def scenario() -> None:
        user_id: UUID | None = None
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                user_id = await authenticate_test_client(client)
                async with get_session_factory()() as session:
                    for index in range(3):
                        essay = Essay(
                            author_id=user_id,
                            title=f"正式作文 {index + 1}",
                            original_text="这是一篇用于验证真实历史推荐来源的作文。",
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
                                dimension_scores=[
                                    {"dimension": "content_and_ideas", "score": 20, "max_score": 25},
                                    {"dimension": "structure_and_coherence", "score": 18, "max_score": 25},
                                    {"dimension": "language_and_expression", "score": 20, "max_score": 25},
                                    {"dimension": "writing_conventions", "score": 20, "max_score": 25},
                                ],
                                aggregation_config={
                                    "learning_feedback": {
                                        "priority_issues": [
                                            {
                                                "category": "content",
                                                "issue_type": "development",
                                                "comment": "论据和观点之间的联系还没有充分展开。",
                                                "suggestion": "补充分析，解释材料为什么能够证明观点。",
                                            }
                                        ]
                                    }
                                },
                            )
                        )
                    await session.commit()

                response = await client.get("/api/training/recommendations")
                assert response.status_code == 200, response.text
                payload = response.json()
                assert payload["personalized"] is True
                assert payload["evaluated_work_count"] == 3
                assert payload["items"][0]["exercise_type"] == "evidence_development"
                assert payload["items"][0]["evidence_work_count"] == 3
                assert "最近 3 篇不同作文" in payload["items"][0]["reason"]
        finally:
            await delete_test_user(user_id)
            await get_engine().dispose()
            get_session_factory.cache_clear()
            get_engine.cache_clear()

    asyncio.run(scenario())
