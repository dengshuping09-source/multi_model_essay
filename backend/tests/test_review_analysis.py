from app.modules.reviews.analysis import aggregate_outputs
from app.modules.reviews.contracts import (
    DimensionScore,
    EssayReviewOutput,
    EvidenceItem,
    ImprovementSuggestion,
)


def make_output(score: float) -> EssayReviewOutput:
    dimensions = [
        DimensionScore(
            dimension=dimension,
            score=score / 4,
            max_score=25,
            rationale="test rationale",
            evidence=[EvidenceItem(quote="essay", rationale="test evidence")],
        )
        for dimension in (
            "content_and_ideas",
            "structure_and_coherence",
            "language_and_expression",
            "writing_conventions",
        )
    ]
    return EssayReviewOutput(
        overall_score=score,
        summary="test summary",
        dimension_scores=dimensions,
        improvement_suggestions=[
            ImprovementSuggestion(
                priority="low", category="language", suggestion="test suggestion"
            )
        ],
    )


def test_aggregation_flags_a_clear_outlier_and_preserves_partial_coverage() -> None:
    aggregate = aggregate_outputs(
        [("deepseek", make_output(84)), ("qwen", make_output(82)), ("doubao", make_output(48))],
        expected_count=3,
    )

    assert aggregate.excluded_provider_keys == ["doubao"]
    assert aggregate.overall_score == 83
    assert aggregate.disputes
    assert 0 < aggregate.confidence <= 1
    assert aggregate.confidence_factors["completed_provider_count"] == 3
    assert aggregate.confidence_factors["excluded_provider_keys"] == ["doubao"]


def test_aggregation_reduces_confidence_when_only_one_provider_completes() -> None:
    aggregate = aggregate_outputs([("deepseek", make_output(80))], expected_count=3)

    assert aggregate.overall_score == 80
    assert aggregate.consistency == "low"
    assert aggregate.confidence < 0.55


def test_aggregation_uses_supplied_calibration_weights_without_hiding_spread() -> None:
    aggregate = aggregate_outputs(
        [("deepseek", make_output(80)), ("qwen", make_output(60))],
        expected_count=2,
        weights={"deepseek": 3.0, "qwen": 1.0},
    )

    assert aggregate.overall_score == 75
    assert aggregate.dimensions[0]["spread"] == 5
