from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DimensionCode = Literal[
    "content_and_ideas",
    "structure_and_coherence",
    "language_and_expression",
    "writing_conventions",
]
Severity = Literal["low", "medium", "high"]
IssueType = Literal["typo", "grammar", "punctuation", "wording", "sentence", "other"]

DIMENSION_CODES: set[str] = {
    "content_and_ideas",
    "structure_and_coherence",
    "language_and_expression",
    "writing_conventions",
}


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str = Field(min_length=1, max_length=1_000)
    rationale: str = Field(min_length=1, max_length=2_000)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> EvidenceItem:
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("start_offset and end_offset must be provided together")
        if self.start_offset is not None and self.end_offset is not None:
            if self.end_offset <= self.start_offset:
                raise ValueError("end_offset must be greater than start_offset")
        return self


class DimensionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: DimensionCode
    score: float = Field(ge=0, le=25)
    max_score: Literal[25]
    rationale: str = Field(min_length=1, max_length=2_000)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=4)


class ReviewAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["content", "structure", "language", "expression", "conventions"]
    kind: Literal["improvement", "strength"] = "improvement"
    issue_type: IssueType | None = None
    severity: Severity
    quote: str = Field(min_length=1, max_length=1_000)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=1)
    comment: str = Field(min_length=1, max_length=2_000)
    suggestion: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_offsets(self) -> ReviewAnnotation:
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("start_offset and end_offset must be provided together")
        if self.start_offset is not None and self.end_offset is not None:
            if self.end_offset <= self.start_offset:
                raise ValueError("end_offset must be greater than start_offset")
        return self


class ImprovementSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Severity
    category: Literal["content", "structure", "language", "expression", "conventions"]
    suggestion: str = Field(min_length=1, max_length=2_000)
    example_revision: str | None = Field(default=None, max_length=2_000)


class EssayReviewOutput(BaseModel):
    """Stable provider-neutral contract used by each independent model review."""

    model_config = ConfigDict(extra="forbid")

    overall_score: float = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=4_000)
    dimension_scores: list[DimensionScore] = Field(min_length=4, max_length=4)
    annotations: list[ReviewAnnotation] = Field(default_factory=list, max_length=12)
    improvement_suggestions: list[ImprovementSuggestion] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_score_dimensions(self) -> EssayReviewOutput:
        dimensions = [item.dimension for item in self.dimension_scores]
        if set(dimensions) != DIMENSION_CODES or len(set(dimensions)) != len(DIMENSION_CODES):
            raise ValueError("dimension_scores must contain every required dimension exactly once")
        dimension_total = round(sum(item.score for item in self.dimension_scores), 2)
        if round(self.overall_score, 2) != dimension_total:
            raise ValueError("overall_score must equal the sum of dimension scores")
        return self


class DeepDimensionDetail(BaseModel):
    """Additional evidence for an existing score; it never recalculates that score."""

    model_config = ConfigDict(extra="forbid")

    dimension: DimensionCode
    explanation: str = Field(min_length=1, max_length=2_000)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=4)


class DeepAnalysisOutput(BaseModel):
    """Optional report enrichment generated after the core evaluation is available."""

    model_config = ConfigDict(extra="forbid")

    overall_analysis: str = Field(min_length=1, max_length=2_000)
    annotations: list[ReviewAnnotation] = Field(default_factory=list, max_length=16)
    dimension_details: list[DeepDimensionDetail] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_dimension_details(self) -> DeepAnalysisOutput:
        dimensions = [item.dimension for item in self.dimension_details]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("dimension_details must not repeat a dimension")
        return self


def parse_essay_review_output(payload: str | dict[str, Any]) -> EssayReviewOutput:
    """Parse a model response while normalising only unambiguous wire-format drift.

    Providers sometimes add a Markdown fence, a short sentence around the JSON,
    an extra field, or calculate the displayed total a little differently.  We
    keep the strict review contract, but do not discard a complete useful review
    for those transport-level variations.  Missing dimensions or a summary are
    still rejected rather than invented.
    """
    source = _json_object_from_payload(payload)
    normalized: dict[str, Any] = {
        key: source[key]
        for key in (
            "overall_score",
            "summary",
            "dimension_scores",
            "annotations",
            "improvement_suggestions",
        )
        if key in source
    }

    if isinstance(normalized.get("summary"), str):
        normalized["summary"] = normalized["summary"].strip()

    if isinstance(normalized.get("dimension_scores"), list):
        normalized["dimension_scores"] = [
            _normalise_dimension_score(item)
            for item in normalized["dimension_scores"]
            if isinstance(item, dict)
        ]
        # The dimensions are the source of truth.  Recalculate the total so a
        # harmless arithmetic difference in a provider response does not make
        # an otherwise valid evaluation unusable.
        if len(normalized["dimension_scores"]) == 4:
            try:
                normalized["overall_score"] = round(
                    sum(float(item["score"]) for item in normalized["dimension_scores"]), 2
                )
            except (KeyError, TypeError, ValueError):
                pass

    annotations = normalized.get("annotations")
    if annotations is None:
        normalized["annotations"] = []
    elif isinstance(annotations, list):
        # Sentence annotations are optional in the quick contract.  A malformed
        # optional item must not invalidate otherwise complete core scores.
        normalized["annotations"] = _validated_optional_items(
            annotations,
            ReviewAnnotation,
            {
                "category",
                "kind",
                "issue_type",
                "severity",
                "quote",
                "start_offset",
                "end_offset",
                "comment",
                "suggestion",
            },
        )

    suggestions = normalized.get("improvement_suggestions")
    if suggestions is None:
        normalized["improvement_suggestions"] = []
    elif isinstance(suggestions, list):
        normalized["improvement_suggestions"] = _validated_optional_items(
            suggestions,
            ImprovementSuggestion,
            {"priority", "category", "suggestion", "example_revision"},
        )

    return EssayReviewOutput.model_validate(normalized)


def parse_json_object(payload: str | dict[str, Any]) -> dict[str, Any]:
    """Expose the tolerant JSON-object extraction used by structured review calls."""

    return _json_object_from_payload(payload)


def _normalise_dimension_score(value: dict[str, Any]) -> dict[str, Any]:
    item = _pick_fields(value, {"dimension", "score", "max_score", "rationale", "evidence"})
    # Every dimension is defined on the same fixed 25-point scale.  Supplying
    # the omitted constant is deterministic and does not manufacture a score.
    if item.get("max_score") is None:
        item["max_score"] = 25
    if isinstance(item.get("max_score"), str):
        try:
            item["max_score"] = int(float(item["max_score"].strip()))
        except ValueError:
            pass
    if item.get("evidence") is None:
        item["evidence"] = []
    elif isinstance(item.get("evidence"), list):
        # Evidence is useful but not a core score field. Providers sometimes
        # emit an empty placeholder object; discard only that optional object.
        item["evidence"] = _validated_optional_items(
            item["evidence"],
            EvidenceItem,
            {"quote", "rationale", "start_offset", "end_offset"},
        )
    return item


def _validated_optional_items(
    values: list[Any],
    schema: type[BaseModel],
    fields: set[str],
) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        candidate = _pick_fields(value, fields)
        # Offsets are optional metadata. Keep an exact pair only when it forms
        # a valid positive range; otherwise retain the textual evidence alone.
        start = candidate.get("start_offset")
        end = candidate.get("end_offset")
        try:
            start_value = int(start) if start is not None else None
            end_value = int(end) if end is not None else None
        except (TypeError, ValueError):
            start_value = end_value = None
        if (
            start_value is None
            or end_value is None
            or start_value < 0
            or end_value <= start_value
        ):
            candidate.pop("start_offset", None)
            candidate.pop("end_offset", None)
        else:
            candidate["start_offset"] = start_value
            candidate["end_offset"] = end_value
        try:
            valid.append(schema.model_validate(candidate).model_dump(mode="json"))
        except ValueError:
            continue
    return valid


def _pick_fields(value: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    return {key: value[key] for key in fields if key in value}


def _json_object_from_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("review content is empty")

    text = payload.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Find the first balanced object, respecting quoted strings and escapes.
    start = text.find("{")
    while start != -1:
        depth = 0
        quoted = False
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
                continue
            if character == '"':
                quoted = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : index + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = text.find("{", start + 1)
    raise ValueError("review content does not contain a JSON object")


class PolishChange(BaseModel):
    """One bounded expression-level change that can be explained to a student."""

    model_config = ConfigDict(extra="forbid")

    original: str = Field(min_length=1, max_length=1_000)
    revised: str = Field(min_length=1, max_length=1_000)
    reason: str = Field(min_length=1, max_length=1_000)
    category: Literal["wording", "sentence", "detail", "structure", "conventions"]


class EssayPolishOutput(BaseModel):
    """A conservative polish that preserves the student's content and voice."""

    model_config = ConfigDict(extra="forbid")

    polished_text: str = Field(min_length=1, max_length=50_000)
    overview: str = Field(min_length=1, max_length=1_000)
    changes: list[PolishChange] = Field(min_length=1, max_length=12)
