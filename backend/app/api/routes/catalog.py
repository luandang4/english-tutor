"""Static catalog: health, options for the UI, preset topics."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.constants import Skill
from app.models.topic import Topic
from app.schemas.api import MetaOut, Option, TopicOut, level_options
from app.services.conversation.live import SCENARIOS, VOICES

router = APIRouter(tags=["catalog"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta", response_model=MetaOut)
async def meta() -> MetaOut:
    return MetaOut(
        levels=level_options(),
        scenarios=[Option(value=k, label=v["label"]) for k, v in SCENARIOS.items()],
        voices=VOICES,
        pronunciation_enabled=get_settings().azure_enabled,
    )


@router.get("/topics", response_model=list[TopicOut])
async def list_topics(session: SessionDep, skill: Skill | None = None) -> list[Topic]:
    q = select(Topic).order_by(Topic.skill, Topic.sort_order, Topic.id)
    if skill:
        q = q.where(Topic.skill == skill)
    return list((await session.scalars(q)).all())
