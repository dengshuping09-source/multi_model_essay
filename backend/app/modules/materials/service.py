from __future__ import annotations

from collections.abc import Iterable

from app.modules.materials.catalog import detected_themes
from app.schemas.material import WritingMaterial


ISSUE_KEYWORDS = {
    "论据展开": ("论据", "展开", "例子", "事例", "材料", "内容单薄"),
    "细节描写": ("细节", "描写", "具体", "画面"),
    "结构组织": ("结构", "段落", "衔接", "提纲"),
}


def _issue_focus(values: Iterable[str | None]) -> set[str]:
    text = " ".join(value.strip() for value in values if isinstance(value, str) and value.strip())
    return {label for label, keywords in ISSUE_KEYWORDS.items() if any(keyword in text for keyword in keywords)}


def _theme_overlap(material: WritingMaterial, themes: set[str]) -> set[str]:
    return set(material.themes).intersection(themes)


def recommend_materials(
    materials: Iterable[WritingMaterial],
    *,
    topic: str | None = None,
    idea: str | None = None,
    issue: str | None = None,
    recurring_issue_labels: Iterable[str] = (),
) -> list[tuple[WritingMaterial, str, list[str]]]:
    """Return a small, explainable, category-diverse set of relevant entries."""

    topic_themes = detected_themes([topic])
    idea_themes = detected_themes([idea])
    current_focus = _issue_focus([issue])
    history_labels = list(recurring_issue_labels)
    historical_focus = _issue_focus(history_labels)
    candidates: list[tuple[int, WritingMaterial, str, list[str]]] = []

    for material in materials:
        score = 0
        reasons: list[str] = []
        sources: list[str] = []
        matched_topic = _theme_overlap(material, topic_themes)
        matched_idea = _theme_overlap(material, idea_themes)
        if matched_topic:
            score += 5 + len(matched_topic)
            reasons.append(f"题目中提到“{sorted(matched_topic)[0]}”，这则素材可以提供具体事实支撑。")
            sources.append("题目")
        if matched_idea:
            score += 4 + len(matched_idea)
            reasons.append(f"你的立意涉及“{sorted(matched_idea)[0]}”，可用它把观点落到具体行动上。")
            sources.append("立意")
        if current_focus:
            if current_focus.intersection({"论据展开", "细节描写"}):
                score += 3
                reasons.append("当前反馈提示内容需要更具体；它适合练习“事实—观点”的连接。")
                sources.append("当前反馈")
            elif "结构组织" in current_focus:
                score += 1
        if historical_focus.intersection({"论据展开", "细节描写"}):
            score += 2
            reasons.append("近期正式评测反复提示内容展开问题，可用它练习从材料提炼观点。")
            sources.append("历史弱项")
        elif "结构组织" in historical_focus:
            score += 1

        if score:
            candidates.append((score, material, " ".join(dict.fromkeys(reasons)), list(dict.fromkeys(sources))))

    if not candidates:
        candidates = [
            (
                0,
                material,
                "先从一则事实清楚、使用边界明确的素材开始，练习把材料与自己的观点连起来。",
                [],
            )
            for material in materials
        ]

    candidates.sort(key=lambda item: (-item[0], item[1].title))
    selected: list[tuple[WritingMaterial, str, list[str]]] = []
    used_categories: set[str] = set()
    for _, material, reason, sources in candidates:
        if material.category in used_categories and len(selected) < 3:
            continue
        selected.append((material, reason, sources))
        used_categories.add(material.category)
        if len(selected) == 4:
            break
    return selected
