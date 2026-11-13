"""Vocabulary & grammar lessons."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, SessionDep, get_or_404, get_owned
from app.core.constants import LessonStatus, Skill
from app.models.lesson import Lesson
from app.models.topic import Topic
from app.models.user import User
from app.schemas.api import AttemptCreate, AttemptOut, DeckAddOut, LessonCreate, LessonDetail, LessonSummary
from app.services import access, srs, topics
from app.services import lessons as svc
from app.services.ai.client import AIUnavailableError

router = APIRouter(prefix="/lessons", tags=["lessons"])
LESSON_SKILLS = (Skill.VOCABULARY, Skill.GRAMMAR)


async def _allowed_skills(session: AsyncSession, user: User) -> list[str]:
    allowed = access.effective_features(user, await access.get_system(session))
    return [s.value for s in LESSON_SKILLS if s.value in allowed]


async def _owned_lesson(session: AsyncSession, lesson_id: int, user: User) -> Lesson:
    """The user's lesson, and the user may use that lesson's skill (vocabulary / grammar)."""
    lesson = await get_owned(session, Lesson, lesson_id, user, "Bài học")
    await access.ensure_feature(session, user, lesson.skill)
    return lesson


@router.post("", response_model=LessonDetail, status_code=status.HTTP_201_CREATED)
async def create_lesson(body: LessonCreate, session: SessionDep, user: CurrentUser) -> LessonDetail:
    if body.custom is None:
        preset = await get_or_404(session, Topic, body.topic_id, "Chủ đề")
        if preset.skill not in (Skill.VOCABULARY, Skill.GRAMMAR):
            raise HTTPException(400, "Chủ đề này không phải bài từ vựng / ngữ pháp.")
        skill = Skill(preset.skill)
    else:
        skill = Skill(body.skill)
    await access.ensure_quota(session, user, skill)
    topic = await topics.topic_for_new_item(session, user.id, skill, body.topic_id, body.custom)
    if topic is None:
        raise HTTPException(404, "Chủ đề không tồn tại.")
    lesson = await svc.create_lesson(session, topic, body.level, user.id)
    await access.record_usage(session, user.id, skill)
    return await svc.lesson_detail(session, lesson)


@router.get("", response_model=list[LessonSummary])
async def list_lessons(
    session: SessionDep, user: CurrentUser, skill: Skill | None = None, limit: int = 50
) -> list[LessonSummary]:
    if skill:
        await access.ensure_feature(session, user, skill)
    allowed = [s for s in (await _allowed_skills(session, user)) if skill in (None, s)]
    q = (
        select(Lesson)
        .where(Lesson.user_id == user.id, Lesson.skill.in_(allowed))
        .order_by(Lesson.id.desc())
        .limit(min(limit, 200))
    )
    return [svc.lesson_summary(lesson) for lesson in (await session.scalars(q)).all()]


@router.get("/{lesson_id}", response_model=LessonDetail)
async def get_lesson(lesson_id: int, session: SessionDep, user: CurrentUser) -> LessonDetail:
    lesson = await _owned_lesson(session, lesson_id, user)
    return await svc.lesson_detail(session, lesson)


@router.post("/{lesson_id}/retry", response_model=LessonDetail)
async def retry_lesson(lesson_id: int, session: SessionDep, user: CurrentUser) -> LessonDetail:
    lesson = await _owned_lesson(session, lesson_id, user)
    if lesson.status != LessonStatus.FAILED:
        raise HTTPException(409, "Chỉ tạo lại được bài học bị lỗi.")
    await access.ensure_quota(session, user, lesson.skill)
    await svc.retry_lesson(session, lesson)
    await access.record_usage(session, user.id, lesson.skill)
    return await svc.lesson_detail(session, lesson)


@router.delete("/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(lesson_id: int, session: SessionDep, user: CurrentUser) -> Response:
    lesson = await _owned_lesson(session, lesson_id, user)
    await session.delete(lesson)
    await session.flush()
    await topics.delete_custom_topic_if_unused(session, lesson.topic_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{lesson_id}/exercises/{exercise_id}/attempts", response_model=AttemptOut)
async def attempt(
    lesson_id: int, exercise_id: str, body: AttemptCreate, session: SessionDep, user: CurrentUser
) -> AttemptOut:
    lesson = await _owned_lesson(session, lesson_id, user)
    if lesson.status not in (LessonStatus.READY, LessonStatus.COMPLETED):
        raise HTTPException(409, "Bài học chưa sẵn sàng.")
    exercise = next((e for e in lesson.exercises if e["id"] == exercise_id), None)
    if exercise is None:
        raise HTTPException(404, "Bài tập không tồn tại.")
    try:
        return await svc.submit_attempt(session, lesson, exercise, body.answer)
    except AIUnavailableError as e:
        raise HTTPException(503, str(e)) from e


@router.post("/{lesson_id}/exercises/regenerate", response_model=LessonDetail)
async def regenerate_exercises(lesson_id: int, session: SessionDep, user: CurrentUser) -> LessonDetail:
    """Create a fresh exercise set (new round) for a lesson that is already generated."""
    lesson = await _owned_lesson(session, lesson_id, user)
    if lesson.status not in (LessonStatus.READY, LessonStatus.COMPLETED):
        raise HTTPException(409, "Bài học chưa sẵn sàng.")
    if lesson.exercises_status == "generating":
        raise HTTPException(409, "Đang tạo bài tập mới, vui lòng đợi.")
    await access.ensure_quota(session, user, lesson.skill)
    await svc.regenerate_exercises(session, lesson)
    await access.record_usage(session, user.id, lesson.skill)
    return await svc.lesson_detail(session, lesson)


@router.post("/{lesson_id}/deck", response_model=DeckAddOut)
async def add_to_deck(lesson_id: int, session: SessionDep, user: CurrentUser) -> DeckAddOut:
    lesson = await _owned_lesson(session, lesson_id, user)
    if lesson.skill != Skill.VOCABULARY or not lesson.content:
        raise HTTPException(400, "Chỉ bài từ vựng đã tạo xong mới thêm được vào bộ ôn tập.")
    added = await srs.add_lesson_words(session, lesson)
    await session.commit()
    return DeckAddOut(added=added, in_deck=await srs.lesson_words_in_deck(session, lesson))
