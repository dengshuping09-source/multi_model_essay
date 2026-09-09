from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SCORING_STANDARD_VERSION = "cn-essay-v2"
PROMPT_VERSION = "essay-review-v3-quick"


@dataclass(frozen=True)
class EssayReviewContext:
    grade_level: str | None
    genre: str | None
    writing_prompt: str | None
    full_score: int
    review_mode: Literal["quick"] = "quick"


def scoring_instruction(context: EssayReviewContext, essay_text: str = "") -> str:
    char_count = len(essay_text.strip())
    details = [
        "Use the shared Chinese composition standard cn-essay-v2.",
        "Scores are normalized to 100 for cross-model comparison: four required dimensions, each 0-25.",
        "Judge the essay in the supplied educational context. The assignment full score is context only; do not change the normalized 100-point contract.",
        f"Grade level: {context.grade_level or 'not supplied'}.",
        f"Genre: {context.genre or 'not supplied'}.",
        f"Writing prompt or requirement: {context.writing_prompt or 'not supplied'}.",
        f"Assignment full score: {context.full_score}.",
        "Do not penalize missing context. Cite only exact excerpts from the submitted essay, and give actionable, age-appropriate suggestions.",
        f"The essay has {char_count} characters.",
        "This is the quick evaluation stage. Keep the summary concise, include at most one exact evidence excerpt per dimension, return no sentence annotations, and provide only 1-3 highest-priority improvement suggestions.",
        "Do not perform a full typo, grammar, punctuation, or sentence-by-sentence scan in this stage. Those are generated separately only when the student requests a deep analysis.",
    ]
    return "\n".join(details)
