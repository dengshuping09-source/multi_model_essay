from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, OptionalCurrentUser
from app.db.models import Essay, EssayStatus, FinalEvaluation, MaterialFavorite, MaterialRecentView, ReviewStatus
from app.db.session import get_db_session
from app.modules.essays.growth import build_growth_summary
from app.modules.materials.catalog import find_material, search_materials
from app.modules.materials.service import recommend_materials
from app.schemas.material import (
    MaterialCategory,
    MaterialFavoriteResponse,
    MaterialListResponse,
    MaterialRecentViewItem,
    MaterialRecentViewListResponse,
    MaterialRecommendation,
    MaterialRecommendationResponse,
    WritingMaterial,
)


router = APIRouter(tags=["writing-materials"])
RECENT_VIEW_LIMIT = 40


def _with_favorite(material: WritingMaterial, favorite_ids: set[str]) -> WritingMaterial:
    return material.model_copy(update={"is_favorited": material.id in favorite_ids})


async def _favorite_ids(session: AsyncSession, user_id: object | None) -> set[str]:
    if user_id is None:
        return set()
    return set(
        (
            await session.scalars(
                select(MaterialFavorite.material_id).where(MaterialFavorite.author_id == user_id)
            )
        ).all()
    )


def _latest_completed_final(essay: Essay) -> FinalEvaluation | None:
    completed = [item for item in essay.final_evaluations if item.status == ReviewStatus.COMPLETED]
    return max(completed, key=lambda item: item.version, default=None)


async def _recurring_issue_labels(session: AsyncSession, user_id: object | None) -> list[str]:
    if user_id is None:
        return []
    essays = list(
        (
            await session.scalars(
                select(Essay)
                .where(Essay.author_id == user_id, Essay.status == EssayStatus.EVALUATED)
                .options(selectinload(Essay.final_evaluations))
            )
        ).all()
    )
    records = [(essay, final) for essay in essays if (final := _latest_completed_final(essay))]
    summary = build_growth_summary(records)
    recurring = summary.get("recurring_issues")
    return [str(item.get("label")) for item in recurring if isinstance(item, dict) and item.get("label")] if isinstance(recurring, list) else []


@router.get("/", response_model=MaterialListResponse)
async def list_materials(
    query: str | None = Query(default=None, max_length=120),
    category: MaterialCategory | None = None,
    theme: str | None = Query(default=None, max_length=30),
    favorites_only: bool = False,
    user: OptionalCurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> MaterialListResponse:
    if favorites_only and user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录后可以查看收藏素材")
    favorite_ids = await _favorite_ids(session, user.id if user else None)
    items = [
        _with_favorite(item, favorite_ids)
        for item in search_materials(query=query, category=category, theme=theme)
    ]
    if favorites_only:
        items = [item for item in items if item.is_favorited]
    return MaterialListResponse(items=items, total=len(items))


@router.get("/recommendations", response_model=MaterialRecommendationResponse)
async def get_material_recommendations(
    topic: str | None = Query(default=None, max_length=2_000),
    idea: str | None = Query(default=None, max_length=2_000),
    issue: str | None = Query(default=None, max_length=1_000),
    user: OptionalCurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> MaterialRecommendationResponse:
    favorite_ids = await _favorite_ids(session, user.id if user else None)
    recurring = await _recurring_issue_labels(session, user.id if user else None)
    recommendations = recommend_materials(
        search_materials(), topic=topic, idea=idea, issue=issue, recurring_issue_labels=recurring
    )
    return MaterialRecommendationResponse(
        items=[
            MaterialRecommendation(
                material=_with_favorite(material, favorite_ids),
                reason=reason,
                sources=sources,
            )
            for material, reason, sources in recommendations
        ],
        personalized=bool(recurring),
        context_available=bool((topic or "").strip() or (idea or "").strip() or (issue or "").strip() or recurring),
    )


@router.get("/recent", response_model=MaterialRecentViewListResponse)
async def list_recent_material_views(
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> MaterialRecentViewListResponse:
    favorite_ids = await _favorite_ids(session, user.id)
    views = list(
        (
            await session.scalars(
                select(MaterialRecentView)
                .where(MaterialRecentView.author_id == user.id)
                .order_by(MaterialRecentView.last_viewed_at.desc())
                .limit(RECENT_VIEW_LIMIT)
            )
        ).all()
    )
    items: list[MaterialRecentViewItem] = []
    for view in views:
        material = find_material(view.material_id)
        if material is not None:
            items.append(
                MaterialRecentViewItem(
                    material=_with_favorite(material, favorite_ids),
                    last_viewed_at=view.last_viewed_at,
                )
            )
    return MaterialRecentViewListResponse(items=items, total=len(items))


@router.put("/{material_id}/recent-view", response_model=MaterialRecentViewItem)
async def record_material_recent_view(
    material_id: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> MaterialRecentViewItem:
    material = find_material(material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这条素材暂时无法查看")
    view = await session.scalar(
        select(MaterialRecentView).where(
            MaterialRecentView.author_id == user.id,
            MaterialRecentView.material_id == material_id,
        )
    )
    if view is None:
        view = MaterialRecentView(
            author_id=user.id, material_id=material_id, last_viewed_at=datetime.now(timezone.utc)
        )
        session.add(view)
    else:
        view.last_viewed_at = datetime.now(timezone.utc)
    await session.flush()
    stale_ids = list(
        (
            await session.scalars(
                select(MaterialRecentView.id)
                .where(MaterialRecentView.author_id == user.id)
                .order_by(MaterialRecentView.last_viewed_at.desc())
                .offset(RECENT_VIEW_LIMIT)
            )
        ).all()
    )
    if stale_ids:
        await session.execute(delete(MaterialRecentView).where(MaterialRecentView.id.in_(stale_ids)))
    await session.commit()
    await session.refresh(view)
    favorite_ids = await _favorite_ids(session, user.id)
    return MaterialRecentViewItem(
        material=_with_favorite(material, favorite_ids), last_viewed_at=view.last_viewed_at
    )


@router.delete("/recent")
async def clear_recent_material_views(
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    await session.execute(delete(MaterialRecentView).where(MaterialRecentView.author_id == user.id))
    await session.commit()
    return {"cleared": True}


@router.get("/{material_id}", response_model=WritingMaterial)
async def get_material(
    material_id: str,
    user: OptionalCurrentUser = None,
    session: AsyncSession = Depends(get_db_session),
) -> WritingMaterial:
    material = find_material(material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这条素材暂时无法查看")
    favorite_ids = await _favorite_ids(session, user.id if user else None)
    return _with_favorite(material, favorite_ids)


@router.put("/{material_id}/favorite", response_model=MaterialFavoriteResponse)
async def favorite_material(
    material_id: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> MaterialFavoriteResponse:
    if find_material(material_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这条素材暂时无法收藏")
    exists = await session.scalar(
        select(MaterialFavorite).where(
            MaterialFavorite.author_id == user.id, MaterialFavorite.material_id == material_id
        )
    )
    if exists is None:
        session.add(MaterialFavorite(author_id=user.id, material_id=material_id))
        await session.commit()
    return MaterialFavoriteResponse(material_id=material_id, is_favorited=True)


@router.delete("/{material_id}/favorite", response_model=MaterialFavoriteResponse)
async def unfavorite_material(
    material_id: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> MaterialFavoriteResponse:
    await session.execute(
        delete(MaterialFavorite).where(
            MaterialFavorite.author_id == user.id, MaterialFavorite.material_id == material_id
        )
    )
    await session.commit()
    return MaterialFavoriteResponse(material_id=material_id, is_favorited=False)
