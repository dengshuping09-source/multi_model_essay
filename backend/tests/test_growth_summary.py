from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.modules.essays.growth import build_growth_summary
from app.schemas.essay import EssayGrowthSummaryResponse


BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
DIMENSION_NAMES = (
    "content_and_ideas",
    "structure_and_coherence",
    "language_and_expression",
    "writing_conventions",
)


def make_record(
    *,
    day: int,
    scores: tuple[float, float, float, float],
    issues: list[dict] | None = None,
    essay_id=None,
    root_id=None,
    parent_id=None,
    version_no: int = 1,
    text: str = "测试作文。",
    title: str | None = None,
):
    essay_id = essay_id or uuid4()
    root_id = root_id or essay_id
    created_at = BASE_TIME + timedelta(days=day)
    essay = SimpleNamespace(
        id=essay_id,
        root_essay_id=root_id,
        parent_essay_id=parent_id,
        version_no=version_no,
        original_text=text,
        title=title or f"作文{day}",
        created_at=created_at,
    )
    final = SimpleNamespace(
        overall_score=sum(scores),
        dimension_scores=[
            {"dimension": dimension, "score": score, "max_score": 25}
            for dimension, score in zip(DIMENSION_NAMES, scores, strict=True)
        ],
        aggregation_config={
            "learning_feedback": {"priority_issues": issues or []},
            "deep_analysis": {"basic_expression_issues": []},
        },
        created_at=created_at,
    )
    return essay, final


def test_one_work_shows_snapshot_without_long_term_claims() -> None:
    result = build_growth_summary([make_record(day=1, scores=(20, 18, 19, 21))])

    assert result["evaluation_count"] == 1
    assert result["work_count"] == 1
    assert result["additional_works_needed"] == 2
    assert result["has_long_term_insights"] is False
    assert result["recent_improvement_dimension"] is None
    assert result["practice_dimension"] is None
    assert result["recurring_issues"] == []
    assert result["latest"]["dimension_scores"]
    assert result["overall_trend"]["direction"] == "insufficient"
    assert result["overall_trend"]["points"][0]["score"] == 78


def test_three_works_find_supported_dimension_improvement_and_recurring_theme() -> None:
    records = [
        make_record(
            day=index,
            scores=(19, structure, 18, 20),
            issues=[{"category": "content", "suggestion": statement}],
        )
        for index, structure, statement in (
            (1, 15, "补充人物动作和环境细节。"),
            (2, 18, "事件经过需要更多细节描写。"),
            (3, 21, "可以增加具体动作，让画面更清楚。"),
        )
    ]

    result = build_growth_summary(records)

    assert result["has_long_term_insights"] is True
    assert result["recent_improvement_dimension"] == "structure_and_coherence"
    assert result["practice_issue"]["label"] == "细节描写"
    assert result["practice_issue"]["work_count"] == 3
    structure = next(item for item in result["dimension_trends"] if item["dimension"] == "structure_and_coherence")
    assert structure["direction"] == "improving"
    assert structure["recent_change"] == 3
    assert result["overall_trend"]["direction"] == "improving"


def test_three_stable_works_do_not_invent_improvement() -> None:
    result = build_growth_summary(
        [
            make_record(day=1, scores=(20, 19, 20, 21)),
            make_record(day=2, scores=(20.2, 19.1, 20, 20.8)),
            make_record(day=3, scores=(20.1, 19.2, 20.1, 20.9)),
        ]
    )

    assert result["has_long_term_insights"] is True
    assert result["recent_improvement_dimension"] is None
    assert all(item["direction"] == "steady" for item in result["dimension_trends"])


def test_version_change_reuses_real_comparison_for_improved_issue_and_revision_result() -> None:
    root_id = uuid4()
    first_id = root_id
    first = make_record(
        day=1,
        essay_id=first_id,
        root_id=root_id,
        scores=(19, 19, 19, 18),
        text="我高兴的跳了起来。",
    )
    first[1].aggregation_config["deep_analysis"]["basic_expression_issues"] = [
        {
            "category": "conventions",
            "issue_type": "grammar",
            "quote": "高兴的跳",
            "comment": "修饰动作时应使用“地”。",
            "suggestion": "改为“高兴地跳”。",
        }
    ]
    second = make_record(
        day=2,
        root_id=root_id,
        parent_id=first_id,
        version_no=2,
        scores=(20, 20, 20, 19),
        text="我高兴地跳了起来。",
    )

    result = build_growth_summary([first, second])

    assert result["work_count"] == 1
    assert result["revision_summary"]["comparison_count"] == 1
    assert result["revision_summary"]["improved_count"] == 1
    assert result["improved_issues"][0]["label"] == "句子规范"
    assert result["improved_issues"][0]["previous_version_no"] == 1
    assert result["improved_issues"][0]["current_version_no"] == 2


def test_incomplete_old_dimension_data_degrades_without_error() -> None:
    essay, final = make_record(day=1, scores=(20, 20, 20, 20))
    final.dimension_scores = [
        {"dimension": "content_and_ideas", "score": 20, "max_score": 25},
        {"dimension": "structure_and_coherence", "score": "unknown", "max_score": 25},
    ]

    result = build_growth_summary([(essay, final)])

    assert result["has_long_term_insights"] is False
    assert len(result["dimension_trends"][0]["points"]) == 1
    assert result["dimension_trends"][1]["points"] == []


def test_many_works_keep_recent_readable_window_and_match_api_schema() -> None:
    records = [
        make_record(day=day, scores=(17 + day / 10, 18, 19, 20))
        for day in range(1, 11)
    ]

    result = build_growth_summary(records)
    validated = EssayGrowthSummaryResponse.model_validate(result)
    content_trend = next(
        trend for trend in validated.dimension_trends
        if trend.dimension == "content_and_ideas"
    )

    assert validated.work_count == 10
    assert validated.has_long_term_insights is True
    assert len(validated.overall_trend.points) == 10
    assert len(content_trend.points) == 8
    assert content_trend.points[0].title == "作文3"
