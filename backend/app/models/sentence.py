from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.topic import Topic


class SentenceSet(TimestampMixin, Base):
    """Sentence translation practice: Vietnamese sentences the learner writes in English.

    `items` follows schemas.ai.SentenceItemDraft. Sentences come from a lesson, the learner's deck or a topic.
    """

    __tablename__ = "sentence_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # SentenceSource: lesson | deck | topic | retry
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="SET NULL"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="RESTRICT"), index=True)
    # What the sentences practise (lesson words / grammar, deck words), fixed at creation for the AI prompt.
    focus: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    level: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(20), index=True)  # LessonStatus
    title: Mapped[str] = mapped_column(String(200), default="")
    items: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)

    topic: Mapped[Topic | None] = relationship(lazy="joined")
    attempts: Mapped[list["SentenceAttempt"]] = relationship(
        back_populates="sentence_set", cascade="all, delete-orphan", order_by="SentenceAttempt.id", lazy="selectin"
    )


class SentenceAttempt(TimestampMixin, Base):
    """One graded answer (or a reveal) for one sentence of a set. `result` follows schemas.ai.SentenceGrade."""

    __tablename__ = "sentence_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("sentence_sets.id", ondelete="CASCADE"), index=True)
    item_index: Mapped[int] = mapped_column(Integer)
    answer: Mapped[str] = mapped_column(Text, default="")  # empty for a reveal
    verdict: Mapped[str] = mapped_column(String(20))  # correct | almost | wrong | revealed
    score: Mapped[int] = mapped_column(Integer, default=0)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    graded_by: Mapped[str] = mapped_column(String(60), default="rule")

    sentence_set: Mapped[SentenceSet] = relationship(back_populates="attempts")
