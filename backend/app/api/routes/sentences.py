"""Sentence translation practice (part of Writing): Vietnamese sentence -> learner's English -> AI grading."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, get_owned, require_feature
from app.core.constants import Feature, LessonStatus, SentenceSource, Skill
from app.models.lesson import Lesson
from app.models.sentence import SentenceSet
from app.schemas.api import (
    SentenceAttemptCreate,
    SentenceAttemptOut,
    SentenceSetCreate,
    SentenceSetDetail,
    SentenceSetSummary,
)
from app.services import access, topics
from app.services import sentences as svc
from app.services.ai.client import AIUnavailableError

router = APIRouter(prefix="/writing/sentences", tags=["writing"], dependencies=[require_feature(Feature.WRITING)])
WHAT = "Bộ câu"


@router.post("", response_model=SentenceSetDetail, status_code=status.HTTP_201_CREATED)
async def create_set(body: SentenceSetCreate, session: SessionDep, user: CurrentUser) -> SentenceSetDetail:
    await access.ensure_quota(session, user, Feature.WRITING)
    common = {"user_id": user.id, "level": body.level}
    if body.source == "lesson":
        assert body.lesson_id is not None
        lesson = await get_owned(session, Lesson, body.lesson_id, user, "Bài học")
        if lesson.status not in (LessonStatus.READY, LessonStatus.COMPLETED):
            raise HTTPException(409, "Bài học chưa sẵn sàng.")
        row = await svc.create_set(
            session,
            **common,
            source=SentenceSource.LESSON,
            focus=svc.lesson_focus(lesson),
            title=f"Luyện câu: {lesson.title}",
            lesson_id=lesson.id,
        )
    elif body.source == "deck":
        focus = await svc.deck_focus(session, user.id)
        if focus is None:
            raise HTTPException(409, "Deck của bạn chưa có từ nào. Hãy học một bài từ vựng trước.")
        row = await svc.create_set(
            session, **common, source=SentenceSource.DECK, focus=focus, title="Luyện câu: Ôn deck"
        )
    else:
        topic = await topics.topic_for_new_item(session, user.id, Skill.WRITING, body.topic_id, body.custom)
        if topic is None:
            raise HTTPException(404, "Chủ đề không tồn tại.")
        row = await svc.create_set(
            session,
            **common,
            source=SentenceSource.TOPIC,
            focus=svc.topic_focus(topic),
            title=f"Luyện câu: {topic.title_vi or topic.title}",
            topic_id=topic.id,
        )
    await access.record_usage(session, user.id, Feature.WRITING)
    return svc.set_detail(row)


@router.get("", response_model=list[SentenceSetSummary])
async def list_sets(session: SessionDep, user: CurrentUser, limit: int = 50) -> list[SentenceSetSummary]:
    rows = (
        await session.scalars(
            select(SentenceSet)
            .where(SentenceSet.user_id == user.id)
            .order_by(SentenceSet.id.desc())
            .limit(min(limit, 200))
        )
    ).all()
    return [svc.set_summary(r) for r in rows]


@router.get("/{set_id}", response_model=SentenceSetDetail)
async def get_set(set_id: int, session: SessionDep, user: CurrentUser) -> SentenceSetDetail:
    return svc.set_detail(await get_owned(session, SentenceSet, set_id, user, WHAT))


@router.post("/{set_id}/retry", response_model=SentenceSetDetail)
async def retry_generation(set_id: int, session: SessionDep, user: CurrentUser) -> SentenceSetDetail:
    row = await get_owned(session, SentenceSet, set_id, user, WHAT)
    if row.status != LessonStatus.FAILED:
        raise HTTPException(409, "Chỉ tạo lại được bộ câu bị lỗi.")
    await access.ensure_quota(session, user, Feature.WRITING)
    await svc.retry_generation(session, row)
    await access.record_usage(session, user.id, Feature.WRITING)
    return svc.set_detail(row)


@router.post("/{set_id}/redo-missed", response_model=SentenceSetDetail, status_code=status.HTTP_201_CREATED)
async def redo_missed(set_id: int, session: SessionDep, user: CurrentUser) -> SentenceSetDetail:
    row = await get_owned(session, SentenceSet, set_id, user, WHAT)
    try:
        return svc.set_detail(await svc.create_retry_set(session, row))
    except svc.SentenceError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/{set_id}/items/{index}/attempts", response_model=SentenceAttemptOut)
async def submit_attempt(
    set_id: int, index: int, body: SentenceAttemptCreate, session: SessionDep, user: CurrentUser
) -> SentenceAttemptOut:
    row = await get_owned(session, SentenceSet, set_id, user, WHAT)
    try:
        attempt = await svc.submit_attempt(session, row, index, body.answer, body.hint_used)
    except svc.SentenceError as e:
        raise HTTPException(409, str(e)) from e
    except AIUnavailableError as e:
        raise HTTPException(503, str(e)) from e
    return SentenceAttemptOut.model_validate(attempt)


@router.post("/{set_id}/items/{index}/reveal", response_model=SentenceAttemptOut)
async def reveal(set_id: int, index: int, session: SessionDep, user: CurrentUser) -> SentenceAttemptOut:
    row = await get_owned(session, SentenceSet, set_id, user, WHAT)
    try:
        return SentenceAttemptOut.model_validate(await svc.reveal(session, row, index))
    except svc.SentenceError as e:
        raise HTTPException(409, str(e)) from e


@router.delete("/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_set(set_id: int, session: SessionDep, user: CurrentUser) -> Response:
    row = await get_owned(session, SentenceSet, set_id, user, WHAT)
    topic_id = row.topic_id
    await session.delete(row)
    await session.flush()
    if topic_id is not None:
        await topics.delete_custom_topic_if_unused(session, topic_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
