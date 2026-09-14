from __future__ import annotations

import json

import pytest

from app.modules.reviews.contracts import (
    DeepAnalysisOutput,
    DeepDimensionDetail,
    DimensionScore,
    EssayReviewOutput,
    EvidenceItem,
    ImprovementSuggestion,
    ReviewAnnotation,
)
from app.modules.reviews.deep_analysis import (
    DeepAnalysisResponseFormatError,
    _validated_output,
)
from app.modules.reviews.service import _quick_review_output


ESSAY_TEXT = "春雨落在窗台上，我听见细细的雨声。放学后，我和妈妈一起走回家。"


def full_review_output() -> EssayReviewOutput:
    return EssayReviewOutput(
        overall_score=84,
        summary="文章内容完整，叙事清楚，可以继续补充动作和环境细节。",
        dimension_scores=[
            DimensionScore(
                dimension=dimension,
                score=21,
                max_score=25,
                rationale="判断依据清楚。",
                evidence=[
                    EvidenceItem(quote="春雨落在窗台上", rationale="点明环境。"),
                    EvidenceItem(quote="一起走回家", rationale="交代事件。"),
                ],
            )
            for dimension in (
                "content_and_ideas",
                "structure_and_coherence",
                "language_and_expression",
                "writing_conventions",
            )
        ],
        annotations=[
            ReviewAnnotation(
                category="language",
                kind="improvement",
                issue_type="wording",
                severity="medium",
                quote="一起走回家",
                comment="表达可以更具体。",
                suggestion="补充一路上的动作。",
            )
        ],
        improvement_suggestions=[
            ImprovementSuggestion(
                priority=priority,
                category="language",
                suggestion=f"建议 {index}",
            )
            for index, priority in enumerate(("low", "high", "medium", "low"), start=1)
        ],
    )


def test_quick_review_keeps_core_original_text_feedback() -> None:
    original = full_review_output()
    quick = _quick_review_output(original)

    assert quick.overall_score == original.overall_score
    assert [item.score for item in quick.dimension_scores] == [21, 21, 21, 21]
    assert all(len(item.evidence) == 1 for item in quick.dimension_scores)
    assert [item.quote for item in quick.annotations] == ["一起走回家"]
    assert [item.priority for item in quick.improvement_suggestions] == ["high", "medium", "low"]
    assert original.annotations


def test_quick_review_prioritizes_located_improvements_over_strengths() -> None:
    original = full_review_output().model_copy(
        update={
            "annotations": [
                ReviewAnnotation(
                    category="language",
                    kind="strength",
                    severity="low",
                    quote="春雨落在窗台上",
                    comment="开头有画面感。",
                    suggestion="这处环境描写值得保留。",
                ),
                ReviewAnnotation(
                    category="structure",
                    kind="improvement",
                    severity="high",
                    quote="放学后，我和妈妈一起走回家",
                    comment="事件推进较快，缺少承接。",
                    suggestion="补充转场或人物动作，让叙事更连贯。",
                ),
                ReviewAnnotation(
                    category="language",
                    kind="improvement",
                    severity="medium",
                    quote="一起走回家",
                    comment="表达可以更具体。",
                    suggestion="补充一路上的动作。",
                ),
            ]
        }
    )

    quick = _quick_review_output(original)

    assert [item.kind for item in quick.annotations] == ["improvement", "improvement"]
    assert [item.severity for item in quick.annotations] == ["high", "medium"]


def test_deep_analysis_accepts_only_real_essay_evidence() -> None:
    payload = DeepAnalysisOutput(
        overall_analysis="在已有评分基础上，进一步关注环境描写和动作细节。",
        annotations=[
            ReviewAnnotation(
                category="language",
                kind="strength",
                severity="low",
                quote="春雨落在窗台上",
                comment="画面清楚。",
                suggestion="这处环境描写值得保留。",
            ),
            ReviewAnnotation(
                category="language",
                kind="improvement",
                severity="medium",
                quote="原文里不存在",
                comment="无效引用。",
                suggestion="不应保留。",
            ),
        ],
        dimension_details=[
            DeepDimensionDetail(
                dimension="language_and_expression",
                explanation="环境描写让开头更具体。",
                evidence=[EvidenceItem(quote="春雨落在窗台上", rationale="真实原文依据。")],
            )
        ],
    )

    validated = _validated_output(ESSAY_TEXT, json.dumps(payload.model_dump(mode="json"), ensure_ascii=False))

    assert [item.quote for item in validated.annotations] == ["春雨落在窗台上"]
    assert validated.dimension_details[0].evidence[0].quote == "春雨落在窗台上"


def test_deep_analysis_rejects_payload_without_locatable_evidence() -> None:
    payload = {
        "overall_analysis": "只有泛泛而谈的说明。",
        "annotations": [],
        "dimension_details": [],
    }

    with pytest.raises(DeepAnalysisResponseFormatError):
        _validated_output(ESSAY_TEXT, json.dumps(payload, ensure_ascii=False))


def test_deep_analysis_rejects_english_explanation_for_chinese_essay() -> None:
    payload = {
        "overall_analysis": "Add more details to the middle paragraph.",
        "annotations": [
            {
                "category": "language",
                "kind": "improvement",
                "severity": "medium",
                "quote": "春雨落在窗台上",
                "comment": "画面已经清楚。",
                "suggestion": "保留这处描写。",
            }
        ],
        "dimension_details": [],
    }

    with pytest.raises(DeepAnalysisResponseFormatError):
        _validated_output(ESSAY_TEXT, json.dumps(payload, ensure_ascii=False))
