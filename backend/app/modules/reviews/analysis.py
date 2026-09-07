from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median

from app.modules.reviews.contracts import EssayReviewOutput


DIMENSION_ORDER = (
    "content_and_ideas",
    "structure_and_coherence",
    "language_and_expression",
    "writing_conventions",
)
DISPUTE_SPREAD = 8.0
OUTLIER_DISTANCE = 10.0


@dataclass(frozen=True)
class AggregatedEvaluation:
    overall_score: float
    dimensions: list[dict[str, object]]
    confidence: float
    consistency: str
    disputes: list[dict[str, object]]
    excluded_provider_keys: list[str]
    summary: str
    confidence_factors: dict[str, object]
    learning_feedback: dict[str, object]


def _infer_issue_type(category: str, comment: str) -> str:
    normalized = comment.lower()
    if any(keyword in normalized for keyword in ("错别字", "别字", "错字", "用字")):
        return "typo"
    if any(keyword in normalized for keyword in ("标点", "逗号", "句号", "引号", "顿号")):
        return "punctuation"
    if any(keyword in normalized for keyword in ("病句", "语序", "成分残缺", "搭配不当", "句式")):
        return "grammar"
    if category == "conventions":
        return "other"
    if category == "language":
        return "wording"
    return "sentence"


def _learning_feedback(
    included: list[tuple[str, EssayReviewOutput]],
    outputs: list[tuple[str, EssayReviewOutput]],
) -> dict[str, object]:
    strength_candidates: list[tuple[float, dict[str, object]]] = []
    expression_candidates: list[tuple[float, dict[str, object]]] = []
    for _, output in included:
        for dimension in output.dimension_scores:
            evidence = dimension.evidence[0] if dimension.evidence else None
            strength_candidates.append(
                (
                    dimension.score,
                    {
                        "dimension": dimension.dimension,
                        "comment": dimension.rationale,
                        "evidence": evidence.quote if evidence else None,
                        "evidence_reason": evidence.rationale if evidence else None,
                    },
                )
            )
            for item in dimension.evidence:
                expression_candidates.append(
                    (
                        dimension.score + (1 if dimension.dimension == "language_and_expression" else 0),
                        {
                            "quote": item.quote,
                            "reason": item.rationale,
                            "dimension": dimension.dimension,
                        },
                    )
                )

    strengths: list[dict[str, object]] = []
    seen_dimensions: set[str] = set()
    for _, item in sorted(strength_candidates, key=lambda candidate: candidate[0], reverse=True):
        dimension = str(item["dimension"])
        if dimension in seen_dimensions:
            continue
        seen_dimensions.add(dimension)
        strengths.append(item)
        if len(strengths) == 3:
            break

    excellent_expressions: list[dict[str, object]] = []
    seen_quotes: set[str] = set()
    for _, item in sorted(expression_candidates, key=lambda candidate: candidate[0], reverse=True):
        quote = str(item["quote"]).strip()
        if not quote or quote in seen_quotes:
            continue
        seen_quotes.add(quote)
        excellent_expressions.append(item)
        if len(excellent_expressions) == 4:
            break

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    issue_candidates: list[tuple[int, dict[str, object]]] = []
    seen_suggestions: set[str] = set()
    for _, output in outputs:
        for item in output.improvement_suggestions:
            suggestion = item.suggestion.strip()
            if suggestion in seen_suggestions:
                continue
            seen_suggestions.add(suggestion)
            issue_candidates.append(
                (
                    priority_rank[item.priority],
                    {
                        "priority": item.priority,
                        "category": item.category,
                        "suggestion": suggestion,
                        "example_revision": item.example_revision,
                    },
                )
            )
    priority_issues = [item for _, item in sorted(issue_candidates, key=lambda candidate: candidate[0])[:3]]

    basic_issues: list[dict[str, object]] = []
    seen_basic: set[tuple[str, str]] = set()
    for _, output in outputs:
        for item in output.annotations:
            if item.category not in {"language", "expression", "conventions"} and item.issue_type is None:
                continue
            key = (item.quote, item.comment)
            if key in seen_basic:
                continue
            seen_basic.add(key)
            basic_issues.append(
                {
                    "issue_type": item.issue_type or _infer_issue_type(item.category, item.comment),
                    "category": item.category,
                    "severity": item.severity,
                    "quote": item.quote,
                    "comment": item.comment,
                    "suggestion": item.suggestion,
                    "start_offset": item.start_offset,
                    "end_offset": item.end_offset,
                }
            )
    basic_issues.sort(key=lambda item: priority_rank[str(item["severity"])])
    return {
        "strengths": strengths,
        "excellent_expressions": excellent_expressions,
        "priority_issues": priority_issues,
        "basic_expression_issues": basic_issues[:8],
    }


def _weighted_mean(values: list[tuple[str, float]], weights: dict[str, float] | None) -> float:
    if not weights:
        return mean(value for _, value in values)
    total_weight = sum(max(weights.get(key, 0.0), 0.0) for key, _ in values)
    if total_weight <= 0:
        return mean(value for _, value in values)
    return sum(value * max(weights.get(key, 0.0), 0.0) for key, value in values) / total_weight


def aggregate_outputs(
    outputs: list[tuple[str, EssayReviewOutput]],
    expected_count: int,
    weights: dict[str, float] | None = None,
) -> AggregatedEvaluation:
    provider_scores = {key: output.overall_score for key, output in outputs}
    overall_median = median(provider_scores.values())
    excluded = sorted(
        key for key, score in provider_scores.items() if len(provider_scores) >= 3 and abs(score - overall_median) > OUTLIER_DISTANCE
    )
    included = [(key, output) for key, output in outputs if key not in excluded] or outputs
    dimensions: list[dict[str, object]] = []
    disputes: list[dict[str, object]] = []
    spreads: list[float] = []
    for dimension in DIMENSION_ORDER:
        scores = [next(item.score for item in output.dimension_scores if item.dimension == dimension) for _, output in included]
        spread = round(max(scores) - min(scores), 2)
        spreads.append(spread)
        item = {
            "dimension": dimension,
            "score": round(
                _weighted_mean(
                    [
                        (
                            key,
                            next(score.score for score in output.dimension_scores if score.dimension == dimension),
                        )
                        for key, output in included
                    ],
                    weights,
                ),
                2,
            ),
            "max_score": 25,
            "min_score": round(min(scores), 2),
            "max_observed_score": round(max(scores), 2),
            "spread": spread,
            "provider_scores": {key: next(score.score for score in output.dimension_scores if score.dimension == dimension) for key, output in outputs},
        }
        dimensions.append(item)
        if spread >= DISPUTE_SPREAD:
            disputes.append({"type": "dimension_disagreement", "dimension": dimension, "spread": spread, "provider_scores": item["provider_scores"]})
    if excluded:
        disputes.append({"type": "outlier_score", "providers": excluded, "median_score": overall_median})
    overall_score = round(sum(float(item["score"]) for item in dimensions), 2)
    coverage = min(len(outputs) / max(expected_count, 1), 1.0)
    average_spread = mean(spreads) if spreads else 0.0
    agreement = max(0.0, 1.0 - (average_spread / 15.0))
    confidence = round(max(0.1, min(1.0, coverage * agreement)), 4)
    consistency = "high" if confidence >= 0.8 else "medium" if confidence >= 0.55 else "low"
    representative = min(
        included,
        key=lambda item: abs(item[1].overall_score - overall_score),
    )[1]
    summary = representative.summary
    confidence_factors = {
        "formula": "coverage_x_agreement_v1",
        "completed_provider_count": len(outputs),
        "expected_provider_count": expected_count,
        "coverage_ratio": round(coverage, 4),
        "average_dimension_spread": round(average_spread, 4),
        "agreement_ratio": round(agreement, 4),
        "excluded_provider_keys": excluded,
        "dispute_count": len(disputes),
        "explanation": [
            {
                "factor": "coverage",
                "label": "模型完成度",
                "value": round(coverage, 4),
                "detail": f"{len(outputs)}/{expected_count} 个请求模型返回了可结构化汇总的结果。",
            },
            {
                "factor": "agreement",
                "label": "维度一致性",
                "value": round(agreement, 4),
                "detail": f"四个评分维度的平均分差为 {average_spread:.1f} 分。",
            },
            {
                "factor": "outlier",
                "label": "异常评分",
                "value": 0.0 if excluded else 1.0,
                "detail": (
                    f"已识别并在综合分中谨慎处理异常结果：{', '.join(excluded)}。"
                    if excluded
                    else "未发现与中位数相差超过阈值的异常总分。"
                ),
            },
        ],
    }
    return AggregatedEvaluation(
        overall_score,
        dimensions,
        confidence,
        consistency,
        disputes,
        excluded,
        summary,
        confidence_factors,
        _learning_feedback(included, outputs),
    )
