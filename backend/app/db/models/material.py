from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class MaterialFavorite(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A student's private bookmark for one curated material entry."""

    __tablename__ = "material_favorites"
    __table_args__ = (UniqueConstraint("author_id", "material_id", name="material_favorite_unique"),)

    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    material_id: Mapped[str] = mapped_column(String(80), index=True)

    author: Mapped[Any] = relationship("User", back_populates="material_favorites")
