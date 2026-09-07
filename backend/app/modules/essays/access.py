from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Essay, EssaySource, User


async def get_owned_essay(session: AsyncSession, essay_id: UUID, user: User) -> Essay | None:
    return await session.scalar(
        select(Essay)
        .where(Essay.id == essay_id, Essay.author_id == user.id)
        .options(selectinload(Essay.sources).selectinload(EssaySource.quality_analysis))
    )
