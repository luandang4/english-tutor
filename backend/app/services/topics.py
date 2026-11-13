"""Learner-defined (custom) topics: created with a lesson / writing task, removed with the last one using it."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Skill
from app.models.lesson import Lesson
from app.models.topic import Topic
from app.models.writing import WritingTask
from app.schemas.api import CustomTopicIn

CUSTOM_ICON = "✨"


async def create_custom_topic(session: AsyncSession, skill: Skill, user_id: int, title: str, request: str) -> Topic:
    title = " ".join(title.split())
    topic = Topic(
        slug=f"custom-{uuid.uuid4().hex[:12]}",
        skill=skill,
        title=title,
        title_vi=title,
        description_vi=request.strip(),
        focus=request.strip(),
        icon=CUSTOM_ICON,
        user_id=user_id,
    )
    session.add(topic)
    await session.flush()
    return topic


async def topic_for_new_item(
    session: AsyncSession, user_id: int, skill: Skill, topic_id: int | None, custom: CustomTopicIn | None
) -> Topic | None:
    """Preset topic of the right skill, or a new custom topic. None = preset not found / wrong skill."""
    if custom is not None:
        return await create_custom_topic(session, skill, user_id, custom.title, custom.request)
    topic = await session.get(Topic, topic_id)
    if topic is None or topic.skill != skill or topic.user_id not in (None, user_id):
        return None
    return topic


async def delete_custom_topic_if_unused(session: AsyncSession, topic_id: int) -> None:
    """Call after deleting a lesson / task (before commit)."""
    topic = await session.get(Topic, topic_id)
    if topic is None or not topic.is_custom:
        return
    used = await session.scalar(select(func.count()).select_from(Lesson).where(Lesson.topic_id == topic_id))
    used += await session.scalar(select(func.count()).select_from(WritingTask).where(WritingTask.topic_id == topic_id))
    if not used:
        await session.delete(topic)
