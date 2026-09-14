from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


MicroExerciseType = Literal[
    "opening",
    "outline_structure",
    "evidence_development",
    "paragraph_transition",
    "sentence_revision",
    "ending",
]


class TopicTrainingSubmission(BaseModel):
    topic_prompt: str = Field(min_length=4, max_length=2_000)
    requirement_notes: str = Field(min_length=2, max_length=1_000)
    central_idea: str = Field(min_length=4, max_length=1_000)
    outline: str | None = Field(default=None, max_length=2_000)

    @field_validator("topic_prompt", "requirement_notes", "central_idea")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("outline")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None


class TopicTrainingFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_understanding: Literal["accurate", "mostly_accurate", "needs_revision"]
    idea_clarity: Literal["clear", "developing", "unclear"]
    off_topic_risk: Literal["low", "medium", "high"]
    structure_status: Literal["focused", "mostly_focused", "needs_revision"]
    missing_constraints: list[str] = Field(default_factory=list, max_length=4)
    strengths: list[str] = Field(default_factory=list, max_length=2)
    priority_issue: str = Field(min_length=1, max_length=500)
    guidance: list[str] = Field(min_length=1, max_length=3)
    next_step: str = Field(min_length=1, max_length=500)


class TopicTrainingSessionResponse(BaseModel):
    id: UUID
    training_type: str
    topic_prompt: str
    requirement_notes: str
    central_idea: str
    outline: str | None
    status: Literal["running", "completed", "failed"]
    feedback: TopicTrainingFeedback | None
    attempt_count: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TopicTrainingHistoryResponse(BaseModel):
    items: list[TopicTrainingSessionResponse]


class MicroTrainingTask(BaseModel):
    task_id: str
    exercise_type: MicroExerciseType
    title: str
    goal: str
    prompt: str
    context: str | None = None
    instruction: str
    input_hint: str
    suggested_minutes: int = Field(ge=5, le=10)
    min_characters: int = Field(ge=10, le=300)
    max_characters: int = Field(ge=20, le=800)


class MicroTrainingSubmission(BaseModel):
    task_id: str = Field(min_length=3, max_length=80)
    response_text: str = Field(min_length=10, max_length=2_000)

    @field_validator("task_id", "response_text")
    @classmethod
    def strip_micro_text(cls, value: str) -> str:
        return value.strip()


class MicroTrainingFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    achievement: Literal["excellent", "met", "needs_practice"]
    strengths: list[str] = Field(default_factory=list, max_length=2)
    priority_issue: str = Field(min_length=1, max_length=400)
    suggestions: list[str] = Field(min_length=1, max_length=2)
    recommend_retry: bool
    next_step: str = Field(min_length=1, max_length=400)


class MicroTrainingResult(BaseModel):
    id: UUID
    task: MicroTrainingTask
    response_text: str
    status: Literal["completed", "failed"]
    feedback: MicroTrainingFeedback | None
    completed_at: datetime | None
    created_at: datetime


class TrainingRecommendation(BaseModel):
    exercise_type: MicroExerciseType
    title: str
    reason: str
    personalized: bool
    evidence_work_count: int = Field(ge=0)
    source_label: str | None = None


class TrainingRecommendationResponse(BaseModel):
    personalized: bool
    evaluated_work_count: int = Field(ge=0)
    items: list[TrainingRecommendation]
