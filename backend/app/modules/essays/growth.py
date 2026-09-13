from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from app.db.models import Essay, FinalEvaluation
from app.modules.essays.version_comparison import (
    compare_essay_versions,
    extract_version_issues,
)


DIMENSION_ORDER = (
    "content_and_ideas",
    "structure_and_coherence",
    "language_and_expression",
    "writing_conventions",
)

ISSUE_TYPE_LABELS = {
    "typo": "错别字",
    "punctuation": "标点使用",
    "grammar": "句子规范",
    "wording": "用词表达",
    "sentence": "句子表达",
}

CATEGORY_LABELS = {
    "content": "内容展开",
    "structure": "结构组织",
    "language": "语言表达",
    "expression": "语言表达",
    "conventions": "基础表达规范",
}

ISSUE_THEMES = (
    ("细节描写", ("细节", "描写", "画面", "动作", "环境")),
    ("段落衔接", ("衔接", "过渡", "连贯", "承接")),
    ("内容展开", ("展开", "具体", "充实", "事件")),
    ("中心表达", ("主题", "中心", "立意", "主旨")),
)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, datetime):
        return datetime.min.replace(tzinfo=timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _dimension_values(final: FinalEvaluation) -> dict[str, tuple[float, float]]:
    values: dict[str, tuple[float, float]] = {}
    if not isinstance(final.dimension_scores, list):
        return values
    for item in final.dimension_scores:
        if not isinstance(item, dict) or not isinstance(item.get("dimension"), str):
            continue
        score = item.get("score")
        max_score = item.get("max_score")
        if not isinstance(score, (int, float)) or not isinstance(max_score, (int, float)) or max_score <= 0:
            continue
        values[item["dimension"]] = (float(score), float(max_score))
    return values


def _trend_change(points: list[dict[str, Any]]) -> tuple[str, float | None, float | None]:
    if len(points) < 2:
        return "insufficient", None, None
    normalized = [point["score"] / point["max_score"] for point in points]
    recent_change = round((normalized[-1] - normalized[-2]) * points[-1]["max_score"], 1)
    if len(points) < 3:
        return "insufficient", None, recent_change
    window = min(2, len(points) // 2)
    earlier = sum(normalized[:window]) / window
    recent = sum(normalized[-window:]) / window
    normalized_change = recent - earlier
    display_change = round(normalized_change * points[-1]["max_score"], 1)
    threshold = 0.04
    direction = "improving" if normalized_change >= threshold else "declining" if normalized_change <= -threshold else "steady"
    return direction, display_change, recent_change


def _issue_identity(issue: dict[str, object]) -> tuple[str, str | None, str]:
    category = str(issue.get("category") or "other").lower()
    if category == "expression":
        category = "language"
    issue_type = str(issue["issue_type"]).lower() if issue.get("issue_type") else None
    statement = str(issue.get("statement") or "")
    if issue_type in ISSUE_TYPE_LABELS:
        return category, issue_type, ISSUE_TYPE_LABELS[issue_type]
    for label, keywords in ISSUE_THEMES:
        if any(keyword in statement for keyword in keywords):
            return category, issue_type, label
    return category, issue_type, CATEGORY_LABELS.get(category, "写作表达")


def build_growth_summary(
    records: Iterable[tuple[Essay, FinalEvaluation]],
) -> dict[str, Any]:
    ordered = sorted(
        records,
        key=lambda record: _timestamp(getattr(record[1], "created_at", None) or getattr(record[0], "created_at", None)),
    )
    roots = {essay.root_essay_id for essay, _ in ordered}
    has_long_term_insights = len(roots) >= 3

    overall_points: list[dict[str, Any]] = []
    dimension_points: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for essay, final in ordered:
        evaluated_at = getattr(final, "created_at", None) or getattr(essay, "created_at", None)
        if not isinstance(evaluated_at, datetime):
            continue
        dimensions = _dimension_values(final)
        overall_score = getattr(final, "overall_score", None)
        configured_full_score = getattr(essay, "full_score", None)
        fallback_full_score = sum(max_score for _, max_score in dimensions.values())
        full_score = configured_full_score if isinstance(configured_full_score, (int, float)) else fallback_full_score
        if isinstance(overall_score, (int, float)) and full_score > 0:
            overall_points.append(
                {
                    "essay_id": essay.id,
                    "root_essay_id": essay.root_essay_id,
                    "version_no": essay.version_no,
                    "title": essay.title,
                    "evaluated_at": evaluated_at,
                    "score": float(overall_score),
                    "max_score": float(full_score),
                }
            )
        for dimension, (score, max_score) in dimensions.items():
            dimension_points[dimension].append(
                {
                    "essay_id": essay.id,
                    "root_essay_id": essay.root_essay_id,
                    "version_no": essay.version_no,
                    "title": essay.title,
                    "evaluated_at": evaluated_at,
                    "score": score,
                    "max_score": max_score,
                }
            )

    overall_points = overall_points[-10:]
    overall_direction, overall_change, overall_recent_change = _trend_change(overall_points)
    overall_trend = {
        "direction": overall_direction if has_long_term_insights else "insufficient",
        "change": overall_change if has_long_term_insights else None,
        "recent_change": overall_recent_change,
        "points": overall_points,
    }

    dimension_trends: list[dict[str, Any]] = []
    for dimension in DIMENSION_ORDER:
        points = dimension_points.get(dimension, [])[-8:]
        direction, change, recent_change = _trend_change(points)
        dimension_trends.append(
            {
                "dimension": dimension,
                "direction": direction if has_long_term_insights else "insufficient",
                "change": change if has_long_term_insights else None,
                "recent_change": recent_change,
                "points": points,
            }
        )

    recent_improvement_dimension = None
    if has_long_term_insights:
        improving = [item for item in dimension_trends if item["direction"] == "improving"]
        if improving:
            recent_improvement_dimension = max(improving, key=lambda item: item["change"] or 0)["dimension"]

    practice_dimension = None
    if has_long_term_insights:
        comparable = [item for item in dimension_trends if item["points"]]
        if comparable:
            practice_dimension = min(
                comparable,
                key=lambda item: sum(point["score"] / point["max_score"] for point in item["points"][-3:])
                / len(item["points"][-3:]),
            )["dimension"]

    latest_by_root: dict[object, tuple[Essay, FinalEvaluation]] = {}
    for essay, final in ordered:
        current = latest_by_root.get(essay.root_essay_id)
        if current is None or essay.version_no >= current[0].version_no:
            latest_by_root[essay.root_essay_id] = (essay, final)

    issue_groups: dict[tuple[str, str | None, str], dict[str, Any]] = {}
    for essay, final in latest_by_root.values():
        seen_in_work: set[tuple[str, str | None, str]] = set()
        for issue in extract_version_issues(final):
            identity = _issue_identity(issue)
            group = issue_groups.setdefault(
                identity,
                {
                    "category": identity[0],
                    "issue_type": identity[1],
                    "label": identity[2],
                    "work_ids": set(),
                    "occurrence_count": 0,
                    "latest_statement": "",
                    "latest_at": datetime.min.replace(tzinfo=timezone.utc),
                },
            )
            group["occurrence_count"] += 1
            if identity not in seen_in_work:
                group["work_ids"].add(essay.root_essay_id)
                seen_in_work.add(identity)
            evaluated_at = _timestamp(getattr(final, "created_at", None) or getattr(essay, "created_at", None))
            if evaluated_at >= group["latest_at"]:
                group["latest_at"] = evaluated_at
                group["latest_statement"] = issue["statement"]

    recurring_issues = [
        {
            "category": group["category"],
            "issue_type": group["issue_type"],
            "label": group["label"],
            "work_count": len(group["work_ids"]),
            "occurrence_count": group["occurrence_count"],
            "latest_statement": group["latest_statement"],
        }
        for group in issue_groups.values()
        if len(group["work_ids"]) >= 2
    ]
    recurring_issues.sort(key=lambda item: (-item["work_count"], -item["occurrence_count"], item["label"]))
    recurring_issues = recurring_issues[:4] if has_long_term_insights else []

    by_id = {essay.id: (essay, final) for essay, final in ordered}
    comparisons: list[tuple[Essay, dict[str, Any]]] = []
    improved_issues: list[dict[str, Any]] = []
    for essay, final in ordered:
        previous_record = by_id.get(essay.parent_essay_id)
        if previous_record is None:
            continue
        comparison = compare_essay_versions(previous_record[0], previous_record[1], essay, final)
        comparisons.append((essay, comparison))
        evaluated_at = getattr(final, "created_at", None) or getattr(essay, "created_at", None)
        if not isinstance(evaluated_at, datetime):
            continue
        for change in comparison["improved_issues"]:
            issue = change.get("previous")
            if not isinstance(issue, dict):
                continue
            identity = _issue_identity(issue)
            improved_issues.append(
                {
                    "essay_id": essay.id,
                    "title": essay.title,
                    "previous_version_no": comparison["previous_version_no"],
                    "current_version_no": comparison["current_version_no"],
                    "category": identity[0],
                    "issue_type": identity[1],
                    "label": identity[2],
                    "statement": issue["statement"],
                    "explanation": change["explanation"],
                    "evaluated_at": evaluated_at,
                }
            )
    improved_issues.sort(key=lambda item: item["evaluated_at"], reverse=True)
    improved_issues = improved_issues[:4]

    recent_comparisons = comparisons[-5:]
    outcome_counts = Counter(comparison["outcome"] for _, comparison in recent_comparisons)
    improved_dimension_counts: Counter[str] = Counter()
    for _, comparison in recent_comparisons:
        improved_dimension_counts.update(
            item["dimension"] for item in comparison["dimension_changes"] if item["change"] >= 1
        )
    most_improved_dimension, most_improved_dimension_count = (
        improved_dimension_counts.most_common(1)[0] if improved_dimension_counts else (None, 0)
    )

    latest = None
    if ordered:
        latest_essay, latest_final = ordered[-1]
        evaluated_at = getattr(latest_final, "created_at", None) or getattr(latest_essay, "created_at", None)
        if isinstance(evaluated_at, datetime):
            latest = {
                "essay_id": latest_essay.id,
                "title": latest_essay.title,
                "evaluated_at": evaluated_at,
                "overall_score": float(latest_final.overall_score) if latest_final.overall_score is not None else None,
                "dimension_scores": latest_final.dimension_scores if isinstance(latest_final.dimension_scores, list) else [],
            }

    return {
        "evaluation_count": len(ordered),
        "work_count": len(roots),
        "has_long_term_insights": has_long_term_insights,
        "additional_works_needed": max(0, 3 - len(roots)),
        "latest": latest,
        "recent_improvement_dimension": recent_improvement_dimension,
        "practice_dimension": practice_dimension,
        "practice_issue": recurring_issues[0] if recurring_issues else None,
        "overall_trend": overall_trend,
        "dimension_trends": dimension_trends,
        "recurring_issues": recurring_issues,
        "improved_issues": improved_issues,
        "revision_summary": {
            "comparison_count": len(recent_comparisons),
            "improved_count": outcome_counts["improved"],
            "steady_count": outcome_counts["steady"],
            "declined_count": outcome_counts["declined"],
            "most_improved_dimension": most_improved_dimension,
            "most_improved_dimension_count": most_improved_dimension_count,
        },
    }
