from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.db.models import Essay, FinalEvaluation


DIMENSION_BY_CATEGORY = {
    "content": "content_and_ideas",
    "structure": "structure_and_coherence",
    "language": "language_and_expression",
    "expression": "language_and_expression",
    "conventions": "writing_conventions",
}


def _normalise_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s，。！？；：、,.!?;:'\"“”‘’（）()【】\[\]]+", "", value).lower()


def _similarity(left: object, right: object) -> float:
    left_text = _normalise_text(left)
    right_text = _normalise_text(right)
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()


def _issue_from_payload(payload: object, *, source: str) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    suggestion = payload.get("suggestion")
    comment = payload.get("comment")
    statement = suggestion if isinstance(suggestion, str) and suggestion.strip() else comment
    if not isinstance(statement, str) or not statement.strip():
        return None
    quote = payload.get("quote") or payload.get("evidence_text")
    return {
        "category": str(payload.get("category") or "other"),
        "issue_type": str(payload["issue_type"]) if payload.get("issue_type") else None,
        "statement": statement.strip(),
        "evidence_text": quote.strip() if isinstance(quote, str) and quote.strip() else None,
        "suggestion": suggestion.strip()
        if isinstance(suggestion, str) and suggestion.strip()
        else None,
        "source": source,
    }


def _issue_match_score(left: dict[str, object], right: dict[str, object]) -> float:
    left_category = left.get("category")
    right_category = right.get("category")
    if left_category != right_category and left_category != "other" and right_category != "other":
        return 0.0

    score = 0.25 if left_category == right_category else 0.05
    left_type = left.get("issue_type")
    right_type = right.get("issue_type")
    if left_type and right_type:
        score += 0.2 if left_type == right_type else -0.08
    score += 0.4 * _similarity(left.get("statement"), right.get("statement"))
    left_evidence = left.get("evidence_text")
    right_evidence = right.get("evidence_text")
    if left_evidence and right_evidence:
        score += 0.15 * _similarity(left_evidence, right_evidence)
    return max(0.0, score)


def _append_distinct_issue(items: list[dict[str, object]], candidate: dict[str, object]) -> None:
    if any(
        item.get("category") == candidate.get("category")
        and (
            _similarity(item.get("statement"), candidate.get("statement")) >= 0.82
            or (
                item.get("evidence_text")
                and candidate.get("evidence_text")
                and _similarity(item.get("evidence_text"), candidate.get("evidence_text")) >= 0.88
            )
        )
        for item in items
    ):
        return
    items.append(candidate)


def _version_issues(final: FinalEvaluation) -> list[dict[str, object]]:
    config = final.aggregation_config if isinstance(final.aggregation_config, dict) else {}
    feedback = config.get("learning_feedback") if isinstance(config.get("learning_feedback"), dict) else {}
    deep = config.get("deep_analysis") if isinstance(config.get("deep_analysis"), dict) else {}
    candidates: list[tuple[object, str]] = []
    candidates.extend((item, "priority") for item in feedback.get("priority_issues") or [])
    candidates.extend((item, "expression") for item in feedback.get("basic_expression_issues") or [])
    candidates.extend((item, "expression") for item in deep.get("basic_expression_issues") or [])
    candidates.extend(
        (item, "annotation")
        for item in deep.get("annotations") or []
        if isinstance(item, dict) and item.get("kind", "improvement") == "improvement"
    )

    issues: list[dict[str, object]] = []
    for payload, source in candidates:
        issue = _issue_from_payload(payload, source=source)
        if issue is not None:
            _append_distinct_issue(issues, issue)
    return issues[:12]


def extract_version_issues(final: FinalEvaluation) -> list[dict[str, object]]:
    """Return the structured, deduplicated issues already saved with a final evaluation."""
    return _version_issues(final)


def _dimension_map(final: FinalEvaluation) -> dict[str, float]:
    dimensions = final.dimension_scores if isinstance(final.dimension_scores, list) else []
    return {
        str(item["dimension"]): float(item["score"])
        for item in dimensions
        if isinstance(item, dict)
        and item.get("dimension")
        and isinstance(item.get("score"), (int, float))
    }


def _can_mark_improved(
    issue: dict[str, object],
    current_text: str,
    dimension_changes: list[dict[str, object]],
    current_issues: list[dict[str, object]],
) -> tuple[bool, str | None]:
    same_category_remains = any(
        candidate.get("category") == issue.get("category")
        and (
            not issue.get("issue_type")
            or not candidate.get("issue_type")
            or candidate.get("issue_type") == issue.get("issue_type")
        )
        for candidate in current_issues
    )
    evidence = _normalise_text(issue.get("evidence_text"))
    if evidence and evidence not in _normalise_text(current_text) and not same_category_remains:
        return True, "原来被指出的文字已经修改，本版未再出现同一处表达。"

    dimension = DIMENSION_BY_CATEGORY.get(str(issue.get("category")))
    dimension_change = next(
        (item for item in dimension_changes if item["dimension"] == dimension),
        None,
    )
    if dimension_change and float(dimension_change["change"]) >= 1.5 and not same_category_remains:
        return True, "相关评分维度有所提升，本版也未再指出同类核心问题。"
    return False, None


def compare_essay_versions(
    previous_essay: Essay,
    previous_final: FinalEvaluation,
    current_essay: Essay,
    current_final: FinalEvaluation,
) -> dict[str, Any]:
    previous_score = float(previous_final.overall_score) if previous_final.overall_score is not None else None
    current_score = float(current_final.overall_score) if current_final.overall_score is not None else None
    score_change = (
        round(current_score - previous_score, 1)
        if previous_score is not None and current_score is not None
        else None
    )
    outcome = (
        "unavailable"
        if score_change is None
        else "improved"
        if score_change >= 1
        else "declined"
        if score_change <= -1
        else "steady"
    )

    previous_dimensions = _dimension_map(previous_final)
    current_dimensions = _dimension_map(current_final)
    dimension_changes = [
        {
            "dimension": dimension,
            "before": previous_dimensions[dimension],
            "after": score,
            "change": round(score - previous_dimensions[dimension], 1),
        }
        for dimension, score in current_dimensions.items()
        if dimension in previous_dimensions
    ]

    previous_issues = _version_issues(previous_final)
    current_issues = _version_issues(current_final)
    unmatched_current = set(range(len(current_issues)))
    persistent: list[dict[str, object]] = []
    improved: list[dict[str, object]] = []

    for previous_issue in previous_issues:
        matches = sorted(
            (
                (_issue_match_score(previous_issue, current_issues[index]), index)
                for index in unmatched_current
            ),
            reverse=True,
        )
        best_score, best_index = matches[0] if matches else (0.0, -1)
        if best_score >= 0.48:
            current_issue = current_issues[best_index]
            unmatched_current.remove(best_index)
            persistent.append(
                {
                    "previous": previous_issue,
                    "current": current_issue,
                    "basis": "matched_feedback",
                    "explanation": "新旧两版评测仍指出了同一类问题。",
                }
            )
            continue
        is_improved, explanation = _can_mark_improved(
            previous_issue,
            current_essay.original_text or "",
            dimension_changes,
            current_issues,
        )
        if is_improved:
            improved.append(
                {
                    "previous": previous_issue,
                    "current": None,
                    "basis": "changed_evidence",
                    "explanation": explanation,
                }
            )

    newly_found = [
        {
            "previous": None,
            "current": current_issues[index],
            "basis": "new_feedback",
            "explanation": "这一问题只出现在本版的有效评测反馈中。",
        }
        for index in sorted(unmatched_current)
    ]

    return {
        "root_essay_id": current_essay.root_essay_id,
        "previous_essay_id": previous_essay.id,
        "current_essay_id": current_essay.id,
        "previous_version_no": previous_essay.version_no,
        "current_version_no": current_essay.version_no,
        "previous_score": previous_score,
        "current_score": current_score,
        "score_change": score_change,
        "outcome": outcome,
        "dimension_changes": dimension_changes,
        "improved_issues": improved[:3],
        "persistent_issues": persistent[:3],
        "new_issues": newly_found[:3],
    }
