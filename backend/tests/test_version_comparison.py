from types import SimpleNamespace
from uuid import uuid4

from app.modules.essays.version_comparison import compare_essay_versions


def version(essay_id, version_no: int, text: str, parent_id=None):
    return SimpleNamespace(
        id=essay_id,
        root_essay_id=parent_id or essay_id,
        parent_essay_id=parent_id,
        version_no=version_no,
        original_text=text,
    )


def final(score: float, dimensions: dict[str, float], issues: list[dict]):
    return SimpleNamespace(
        overall_score=score,
        dimension_scores=[
            {"dimension": dimension, "score": value, "max_score": 25}
            for dimension, value in dimensions.items()
        ],
        aggregation_config={
            "learning_feedback": {"priority_issues": issues},
            "deep_analysis": {"basic_expression_issues": []},
        },
    )


DIMENSIONS = {
    "content_and_ideas": 20,
    "structure_and_coherence": 20,
    "language_and_expression": 20,
    "writing_conventions": 20,
}


def test_comparison_marks_persistent_and_new_feedback_from_real_results() -> None:
    root_id = uuid4()
    current_id = uuid4()
    previous = version(root_id, 1, "开头很热闹，中段只有一句话。")
    current = version(current_id, 2, "开头很热闹，中段仍然只有一句话，结尾增加了感受。", root_id)
    previous_final = final(
        79,
        DIMENSIONS,
        [{"category": "content", "suggestion": "补充中段的动作和环境细节。"}],
    )
    current_final = final(
        80,
        {**DIMENSIONS, "content_and_ideas": 21},
        [
            {"category": "content", "suggestion": "中段仍需补充人物动作与环境细节。"},
            {"category": "structure", "suggestion": "结尾与前文的衔接还可以更自然。"},
        ],
    )

    result = compare_essay_versions(previous, previous_final, current, current_final)

    assert result["outcome"] == "improved"
    assert result["score_change"] == 1
    assert len(result["persistent_issues"]) == 1
    assert result["persistent_issues"][0]["current"]["category"] == "content"
    assert len(result["new_issues"]) == 1
    assert result["new_issues"][0]["current"]["category"] == "structure"


def test_comparison_marks_changed_locatable_evidence_as_improved() -> None:
    root_id = uuid4()
    current_id = uuid4()
    previous = version(root_id, 1, "我高兴的跳了起来。")
    current = version(current_id, 2, "我高兴地跳了起来。", root_id)
    previous_final = final(80, DIMENSIONS, [])
    previous_final.aggregation_config["deep_analysis"]["basic_expression_issues"] = [
        {
            "category": "conventions",
            "issue_type": "grammar",
            "quote": "高兴的跳",
            "comment": "修饰动作时应使用“地”。",
            "suggestion": "改为“高兴地跳”。",
        }
    ]
    current_final = final(80.4, DIMENSIONS, [])

    result = compare_essay_versions(previous, previous_final, current, current_final)

    assert result["outcome"] == "steady"
    assert len(result["improved_issues"]) == 1
    assert result["improved_issues"][0]["basis"] == "changed_evidence"
    assert result["persistent_issues"] == []


def test_comparison_handles_score_decline_without_inventing_issue_changes() -> None:
    root_id = uuid4()
    current_id = uuid4()
    previous = version(root_id, 1, "第一版作文。")
    current = version(current_id, 2, "第二版作文。", root_id)
    previous_final = final(83, DIMENSIONS, [])
    current_final = final(79, {**DIMENSIONS, "structure_and_coherence": 16}, [])

    result = compare_essay_versions(previous, previous_final, current, current_final)

    assert result["outcome"] == "declined"
    assert result["score_change"] == -4
    assert result["improved_issues"] == []
    assert result["persistent_issues"] == []
    assert result["new_issues"] == []
