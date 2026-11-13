from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.topic import Topic


class WritingTask(TimestampMixin, Base):
    """AI-generated writing assignment. `prompt` follows schemas.ai.WritingTaskDraft."""

    __tablename__ = "writing_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Owner. Nullable only for rows created before accounts existed (claimed by the first registered user).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="RESTRICT"), index=True)
    level: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(20), index=True)  # LessonStatus (generating/ready/completed/failed)
    title: Mapped[str] = mapped_column(String(200), default="")
    prompt: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)

    topic: Mapped[Topic] = relationship(lazy="joined")
    submissions: Mapped[list["WritingSubmission"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="WritingSubmission.id", lazy="selectin"
    )


class WritingSubmission(TimestampMixin, Base):
    """One draft submitted for a task. `result` follows schemas.ai.WritingFeedback."""

    __tablename__ = "writing_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), index=True)  # SubmissionStatus
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)

    task: Mapped[WritingTask] = relationship(back_populates="submissions")
