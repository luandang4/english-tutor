"""Static catalog: health, options for the UI, preset topics."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.constants import FEATURE_INFO, Skill
from app.models.topic import Topic
from app.schemas.api import FeatureInfo, MetaOut, Option, TopicOut, level_options
from app.services import access
from app.services.conversation.live import SCENARIOS
from app.services.speech import assessment

router = APIRouter(tags=["catalog"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta", response_model=MetaOut)
async def meta(session: SessionDep) -> MetaOut:
    return MetaOut(
        levels=level_options(),
        scenarios=[Option(value=k, label=v["label"]) for k, v in SCENARIOS.items()],
        features=[FeatureInfo(value=k, **v) for k, v in FEATURE_INFO.items()],
        pronunciation_enabled=assessment.available(),
        registration_open=await access.registration_open(session),
    )


@router.get("/topics", response_model=list[TopicOut])
async def list_topics(session: SessionDep, skill: Skill | None = None) -> list[Topic]:
    q = select(Topic).where(Topic.user_id.is_(None)).order_by(Topic.skill, Topic.sort_order, Topic.id)
    if skill:
        q = q.where(Topic.skill == skill)
    return list((await session.scalars(q)).all())
