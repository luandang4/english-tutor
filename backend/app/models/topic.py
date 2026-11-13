from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Topic(TimestampMixin, Base):
    """Preset topic the learner picks; the AI builds a lesson around it (seeded from app/seed/topics.py)."""

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
