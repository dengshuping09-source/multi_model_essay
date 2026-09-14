from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class WritingTrainingSession(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A writing exercise record kept separate from formal essay history."""

    __tablename__ = "writing_training_sessions"

    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    training_type: Mapped[str] = mapped_column(
        String(40), default="topic_and_idea", server_default="topic_and_idea", index=True
    )
    topic_prompt: Mapped[str] = mapped_column(Text)
    requirement_notes: Mapped[str] = mapped_column(Text)
    central_idea: Mapped[str] = mapped_column(Text)
    outline: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="running", server_default="running", index=True
    )
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    provider_key: Mapped[str | None] = mapped_column(String(40))
    model_name: Mapped[str | None] = mapped_column(String(120))
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    author: Mapped[Any] = relationship("User", back_populates="training_sessions")
