from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Topic(TimestampMixin, Base):
    """Topic the AI builds a lesson around: a preset (seeded from app/seed/topics.py, user_id NULL) or a learner's
    own custom topic (user_id set, `focus` = their request). Custom topics never appear in the topic list."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    skill: Mapped[str] = mapped_column(String(20), index=True)  # Skill enum
    title: Mapped[str] = mapped_column(String(120))  # English
    title_vi: Mapped[str] = mapped_column(String(120))
    description_vi: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(16), default="")
    focus: Mapped[str] = mapped_column(Text, default="")  # extra guidance for the AI
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, default=None)

    @property
    def is_custom(self) -> bool:
        return self.user_id is not None
