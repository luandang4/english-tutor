from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UTCDateTime


class ConversationSession(TimestampMixin, Base):
    """A live voice lesson with the tutor; transcript = [{"role": "user"|"tutor", "text": str}]."""

    __tablename__ = "conversation_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Owner. Nullable only for rows created before accounts existed (claimed by the first registered user).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(4))
    scenario: Mapped[str] = mapped_column(String(40))
    voice: Mapped[str] = mapped_column(String(20))
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    turns: Mapped[int] = mapped_column(Integer, default=0)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
