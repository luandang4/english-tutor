from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime
from app.models.topic import Topic


class Lesson(TimestampMixin, Base):
    """AI-generated vocabulary or grammar lesson. `content` follows schemas.ai.*LessonDraft (+ exercise ids)."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Owner. Nullable only for rows created before accounts existed (claimed by the first registered user).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="RESTRICT"), index=True)
    skill: Mapped[str] = mapped_column(String(20), index=True)
    level: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(20), index=True)  # LessonStatus
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Exercises can be regenerated after the lesson: each new set is a "round".
    exercise_round: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    exercises_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "generating" | "failed"
    exercises_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    topic: Mapped[Topic] = relationship(lazy="joined")
    attempts: Mapped[list["ExerciseAttempt"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="ExerciseAttempt.id", lazy="selectin"
    )

    @property
    def exercises(self) -> list[dict[str, Any]]:
        return list((self.content or {}).get("exercises", []))


class ExerciseAttempt(TimestampMixin, Base):
    __tablename__ = "exercise_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(String(20))
    answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[int] = mapped_column(Integer)  # 0-100
    feedback_vi: Mapped[str] = mapped_column(Text, default="")
    corrected_answer: Mapped[str] = mapped_column(Text, default="")
    graded_by: Mapped[str] = mapped_column(String(60), default="rule")  # "rule" or a Gemini model id

    lesson: Mapped[Lesson] = relationship(back_populates="attempts")


class LessonRecheck(TimestampMixin, Base):
    """ "Kiểm tra lại" state of one lesson: the running quiz, the last result and (grammar) the 1-3-7-14 schedule."""

    __tablename__ = "lesson_rechecks"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), unique=True)
    step: Mapped[int] = mapped_column(Integer, default=0)  # grammar: rechecks passed on schedule (0..4)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)  # None = derive from completion
    runs: Mapped[int] = mapped_column(Integer, default=0)
    last_done_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    wrong_items: Mapped[list[str]] = mapped_column(JSON, default=list)  # word keys / exercise ids missed last time
    # The quiz in progress: {"items": [question ids], "full": bool, "answers": {question id: outcome}}
    current: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
