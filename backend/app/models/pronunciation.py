from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PronunciationAttempt(TimestampMixin, Base):
    """Azure Pronunciation Assessment result for one recording."""

    __tablename__ = "pronunciation_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Owner. Nullable only for rows created before accounts existed (claimed by the first registered user).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("vocab_cards.id", ondelete="SET NULL"), index=True)
    reference_text: Mapped[str] = mapped_column(Text)
    recognized_text: Mapped[str] = mapped_column(Text, default="")
    pron_score: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float] = mapped_column(Float)
    fluency: Mapped[float | None] = mapped_column(Float, nullable=True)  # the local engine has none
    completeness: Mapped[float] = mapped_column(Float)
    prosody: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine: Mapped[str] = mapped_column(String(10), default="azure", server_default="azure")
    words: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
