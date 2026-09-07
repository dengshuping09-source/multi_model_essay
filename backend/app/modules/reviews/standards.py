from __future__ import annotations

from dataclasses import dataclass


SCORING_STANDARD_VERSION = "cn-essay-v2"
PROMPT_VERSION = "essay-review-v2"


@dataclass(frozen=True)
class EssayReviewContext:
    grade_level: str | None
    genre: str | None
    writing_prompt: str | None
    full_score: int


def scoring_instruction(context: EssayReviewContext, essay_text: str = "") -> str:
    char_count = len(essay_text.strip())
    if char_count < 250:
        annotation_target = "about 3-5"
    elif char_count < 500:
        annotation_target = "about 4-7"
    elif char_count <= 800:
        annotation_target = "about 6-10"
    else:
        annotation_target = "about 8-12"
    details = [
        "Use the shared Chinese composition standard cn-essay-v2.",
        "Scores are normalized to 100 for cross-model comparison: four required dimensions, each 0-25.",
        "Judge the essay in the supplied educational context. The assignment full score is context only; do not change the normalized 100-point contract.",
        f"Grade level: {context.grade_level or 'not supplied'}.",
        f"Genre: {context.genre or 'not supplied'}.",
        f"Writing prompt or requirement: {context.writing_prompt or 'not supplied'}.",
        f"Assignment full score: {context.full_score}.",
        "Do not penalize missing context. Cite only exact excerpts from the submitted essay, and give actionable, age-appropriate suggestions.",
        f"The essay has {char_count} characters. Aim for {annotation_target} high-value annotations when the content supports them; use fewer when there are fewer meaningful points and never manufacture issues to hit a quota.",
        "Include a small number of kind=strength annotations for exact sentences worth keeping, alongside kind=improvement annotations for real problems.",
    ]
    return "\n".join(details)
