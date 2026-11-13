from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime


class VocabCard(TimestampMixin, Base):
    """A word in the learner's spaced-repetition deck (FSRS)."""

    __tablename__ = "vocab_cards"
    __table_args__ = (UniqueConstraint("user_id", "word_key", name="uq_vocab_cards_user_word"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Owner. Nullable only for rows created before accounts existed (claimed by the first registered user).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="SET NULL"), index=True)
    word_key: Mapped[str] = mapped_column(String(120))  # lower-cased word, unique per user
    word: Mapped[str] = mapped_column(String(120))
    ipa: Mapped[str] = mapped_column(String(120), default="")
    part_of_speech: Mapped[str] = mapped_column(String(40), default="")
    meaning_vi: Mapped[str] = mapped_column(Text, default="")
    definition_en: Mapped[str] = mapped_column(Text, default="")
    example_en: Mapped[str] = mapped_column(Text, default="")
    example_vi: Mapped[str] = mapped_column(Text, default="")

    fsrs_card: Mapped[dict[str, Any]] = mapped_column(JSON)  # fsrs.Card.to_dict()
    due_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    reviews: Mapped[list["ReviewLog"]] = relationship(back_populates="card", cascade="all, delete-orphan")


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("vocab_cards.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1 Again, 2 Hard, 3 Good, 4 Easy
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)

    card: Mapped[VocabCard] = relationship(back_populates="reviews")
