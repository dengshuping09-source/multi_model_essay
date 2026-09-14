from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MaterialCategory = Literal["人物", "事件", "历史", "科技", "文化", "社会", "青春成长"]


class MaterialReference(BaseModel):
    """A curated, verifiable reading link. Links are never generated at request time."""

    title: str = Field(min_length=1, max_length=160)
    publisher: str = Field(min_length=1, max_length=80)
    url: str = Field(pattern=r"^https://", max_length=500)


class WritingMaterial(BaseModel):
    """A curated, compact source of evidence rather than a model-generated anecdote."""

    id: str
    title: str
    category: MaterialCategory
    source_kind: Literal["公共事实", "生活观察"]
    background: str
    core_facts: list[str] = Field(min_length=1, max_length=4)
    themes: list[str] = Field(min_length=1, max_length=6)
    supports_claims: list[str] = Field(min_length=1, max_length=4)
    how_to_use: str
    common_misuse: str
    example_use: str
    fact_check_note: str
    reference_links: list[MaterialReference] = Field(default_factory=list, max_length=3)
    is_favorited: bool = False


class MaterialListResponse(BaseModel):
    items: list[WritingMaterial]
    total: int


class MaterialRecommendation(BaseModel):
    material: WritingMaterial
    reason: str
    sources: list[Literal["题目", "立意", "当前反馈", "历史弱项"]]


class MaterialRecommendationResponse(BaseModel):
    items: list[MaterialRecommendation]
    personalized: bool
    context_available: bool


class MaterialFavoriteResponse(BaseModel):
    material_id: str
    is_favorited: bool
