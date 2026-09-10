from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.reviews.contracts import parse_essay_review_output


def _core_payload() -> dict[str, object]:
    return {
        "overall_score": "80",
        "summary": "  主题明确，叙事完整。  ",
        "dimension_scores": [
            {
                "dimension": dimension,
                "score": "20",
                "rationale": "判断依据明确。",
                "evidence": [],
            }
            for dimension in (
                "content_and_ideas",
                "structure_and_coherence",
                "language_and_expression",
                "writing_conventions",
            )
        ],
    }


def test_optional_empty_evidence_does_not_discard_core_scores() -> None:
    payload = _core_payload()
    payload["dimension_scores"][0]["evidence"] = [
        {"quote": "", "rationale": "", "start_offset": 0, "end_offset": 0}
    ]
    payload["improvement_suggestions"] = [
        {"priority": "high", "category": "language", "suggestion": "补充动作细节。"},
        {"priority": "high", "suggestion": "缺少分类的无效可选项"},
    ]

    output = parse_essay_review_output(payload)

    assert output.overall_score == 80
    assert output.summary == "主题明确，叙事完整。"
    assert output.dimension_scores[0].max_score == 25
    assert output.dimension_scores[0].evidence == []
    assert [item.suggestion for item in output.improvement_suggestions] == ["补充动作细节。"]


def test_missing_core_dimension_still_fails_validation() -> None:
    payload = _core_payload()
    payload["dimension_scores"] = payload["dimension_scores"][:3]

    with pytest.raises(ValidationError):
        parse_essay_review_output(payload)
