"""Vocabulary & grammar lessons."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, get_or_404, get_owned
from app.core.constants import LessonStatus, Skill
from app.models.lesson import Lesson
from app.models.topic import Topic
from app.schemas.api import AttemptCreate, AttemptOut, DeckAddOut, LessonCreate, LessonDetail, LessonSummary
from app.services import lessons as svc
from app.services import srs
from app.services.ai.client import AIUnavailableError

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.post("", response_model=LessonDetail, status_code=status.HTTP_201_CREATED)
async def create_lesson(body: LessonCreate, session: SessionDep, user: CurrentUser) -> LessonDetail:
    topic = await get_or_404(session, Topic, body.topic_id, "Chủ đề")
    if topic.skill not in (Skill.VOCABULARY, Skill.GRAMMAR):
        raise HTTPException(400, "Chủ đề này không phải bài từ vựng / ngữ pháp.")
    lesson = await svc.create_lesson(session, topic, body.level, user.id)
    return await svc.lesson_detail(session, lesson)


@router.get("", response_model=list[LessonSummary])
async def list_lessons(
    session: SessionDep, user: CurrentUser, skill: Skill | None = None, limit: int = 50
) -> list[LessonSummary]:
    q = select(Lesson).where(Lesson.user_id == user.id).order_by(Lesson.id.desc()).limit(min(limit, 200))
    if skill:
        q = q.where(Lesson.skill == skill)
    return [svc.lesson_summary(lesson) for lesson in (await session.scalars(q)).all()]


@router.get("/{lesson_id}", response_model=LessonDetail)
async def get_lesson(lesson_id: int, session: SessionDep, user: CurrentUser) -> LessonDetail:
    lesson = await get_owned(session, Lesson, lesson_id, user, "Bài học")
    return await svc.lesson_detail(session, lesson)


@router.post("/{lesson_id}/retry", response_model=LessonDetail)
async def retry_lesson(lesson_id: int, session: SessionDep, user: CurrentUser) -> LessonDetail:
    lesson = await get_owned(session, Lesson, lesson_id, user, "Bài học")
    if lesson.status != LessonStatus.FAILED:
        raise HTTPException(409, "Chỉ tạo lại được bài học bị lỗi.")
    await svc.retry_lesson(session, lesson)
    return await svc.lesson_detail(session, lesson)


@router.delete("/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(lesson_id: int, session: SessionDep, user: CurrentUser) -> Response:
    lesson = await get_owned(session, Lesson, lesson_id, user, "Bài học")
    await session.delete(lesson)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{lesson_id}/exercises/{exercise_id}/attempts", response_model=AttemptOut)
async def attempt(
    lesson_id: int, exercise_id: str, body: AttemptCreate, session: SessionDep, user: CurrentUser
) -> AttemptOut:
    lesson = await get_owned(session, Lesson, lesson_id, user, "Bài học")
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
    lesson = await get_owned(session, Lesson, lesson_id, user, "Bài học")
    if lesson.status not in (LessonStatus.READY, LessonStatus.COMPLETED):
        raise HTTPException(409, "Bài học chưa sẵn sàng.")
    if lesson.exercises_status == "generating":
        raise HTTPException(409, "Đang tạo bài tập mới, vui lòng đợi.")
    await svc.regenerate_exercises(session, lesson)
    return await svc.lesson_detail(session, lesson)


@router.post("/{lesson_id}/deck", response_model=DeckAddOut)
async def add_to_deck(lesson_id: int, session: SessionDep, user: CurrentUser) -> DeckAddOut:
    lesson = await get_owned(session, Lesson, lesson_id, user, "Bài học")
    if lesson.skill != Skill.VOCABULARY or not lesson.content:
        raise HTTPException(400, "Chỉ bài từ vựng đã tạo xong mới thêm được vào bộ ôn tập.")
    added = await srs.add_lesson_words(session, lesson)
    await session.commit()
    return DeckAddOut(added=added, in_deck=await srs.lesson_words_in_deck(session, lesson))
