"""Static catalog: health, options for the UI, preset topics."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.constants import FEATURE_INFO, Skill
from app.models.topic import Topic
from app.schemas.api import FeatureInfo, MetaOut, PhraseOut, ScenarioOption, TopicOut, level_options
from app.services import access
from app.services.conversation.scenarios import SCENARIOS, Phrase, Scenario

router = APIRouter(tags=["catalog"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta", response_model=MetaOut)
async def meta(session: SessionDep) -> MetaOut:
    return MetaOut(
        levels=level_options(),
        scenarios=[_scenario_option(k, v) for k, v in SCENARIOS.items()],
        features=[FeatureInfo(value=k, **v) for k, v in FEATURE_INFO.items()],
        pronunciation_enabled=get_settings().azure_enabled,
        registration_open=await access.registration_open(session),
    )


def _phrases(items: tuple[Phrase, ...]) -> list[PhraseOut]:
    return [PhraseOut(en=en, vi=vi) for en, vi in items]


def _scenario_option(key: str, s: Scenario) -> ScenarioOption:
    return ScenarioOption(
        value=key,
        label=s.label,
        group=s.group,
        goal_vi=s.goal_vi,
        emma_role_vi=s.roles_vi[0],
        learner_role_vi=s.roles_vi[1],
        phrases_basic=_phrases(s.basic),
        phrases_advanced=_phrases(s.advanced),
    )


@router.get("/topics", response_model=list[TopicOut])
async def list_topics(session: SessionDep, skill: Skill | None = None) -> list[Topic]:
    q = select(Topic).where(Topic.user_id.is_(None)).order_by(Topic.skill, Topic.sort_order, Topic.id)
    if skill:
        q = q.where(Topic.skill == skill)
    return list((await session.scalars(q)).all())
