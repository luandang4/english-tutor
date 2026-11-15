"""Vocabulary deck & spaced-repetition reviews."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, get_owned
from app.api.routes.tts import word_audio
from app.core.config import get_settings
from app.core.constants import Skill
from app.db.base import utcnow
from app.models.lesson import Lesson
from app.models.vocab import VocabCard
from app.schemas.api import (
    AnswerIn,
    AnswerOut,
    CardAddOut,
    CardCreate,
    CardOut,
    DeckStats,
    DueCount,
    LessonReviewStats,
    ReviewCreate,
    ReviewForecast,
    SessionMode,
    SessionOut,
    SrsSettingsIO,
)
from app.services import quiz, review_session, review_stats, srs, word_info
from app.services.ai.client import AIUnavailableError

router = APIRouter(prefix="/vocab", tags=["vocabulary"])


def local_day_start() -> datetime:
    tz = ZoneInfo(get_settings().timezone)
    return datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/stats", response_model=DeckStats)
async def stats(session: SessionDep, user: CurrentUser) -> DeckStats:
    return await srs.deck_stats(session, local_day_start(), user.id)


@router.get("/due-count", response_model=DueCount)
async def due_count(session: SessionDep, user: CurrentUser) -> DueCount:
    """Cheap count for the navigation badge."""
    return DueCount(due=await srs.due_count(session, user.id))


@router.get("/forecast", response_model=ReviewForecast)
async def forecast(session: SessionDep, user: CurrentUser) -> ReviewForecast:
    return await review_stats.forecast(session, user.id)


@router.get("/lesson-stats", response_model=list[LessonReviewStats])
async def lesson_stats(session: SessionDep, user: CurrentUser, skill: Skill | None = None) -> list[LessonReviewStats]:
    return await review_stats.lesson_stats(session, user.id, skill)


@router.get("/settings", response_model=SrsSettingsIO)
async def get_settings_(session: SessionDep, user: CurrentUser) -> SrsSettingsIO:
    row = await srs.get_srs_settings(session, user.id)
    return SrsSettingsIO(desired_retention=row.desired_retention, new_cards_per_day=row.new_cards_per_day)


@router.put("/settings", response_model=SrsSettingsIO)
async def save_settings(body: SrsSettingsIO, session: SessionDep, user: CurrentUser) -> SrsSettingsIO:
    await srs.save_srs_settings(session, user.id, body.desired_retention, body.new_cards_per_day)
    return body


@router.get("/cards", response_model=list[CardOut])
async def list_cards(
    session: SessionDep, user: CurrentUser, due: bool = False, q: str = "", limit: int = 500
) -> list[CardOut]:
    now = utcnow()
    query = select(VocabCard).where(VocabCard.user_id == user.id)
    if due:
        query = query.where(VocabCard.due_at <= now).order_by(VocabCard.due_at)
    else:
        query = query.order_by(VocabCard.created_at.desc())
    if q.strip():
        query = query.where(VocabCard.word_key.contains(q.strip().lower()))
    rows = (await session.scalars(query.limit(min(limit, 1000)))).all()
    lessons = await srs.lessons_by_id(session, {r.lesson_id for r in rows if r.lesson_id})
    scheduler = await srs.scheduler_for(session, user.id)
    return [srs.card_out(r, now, scheduler, lessons.get(r.lesson_id or 0)) for r in rows]


@router.post("/cards", response_model=CardAddOut)
async def add_card(body: CardCreate, session: SessionDep, user: CurrentUser) -> CardAddOut:
    """Add a word by hand. Only `word` is needed: Gemini fills the rest (one Từ vựng request)."""
    try:
        card, created = await word_info.add_user_word(
            session, user, body.model_dump(exclude={"context", "source"}), context=body.context, source=body.source
        )
    except AIUnavailableError as e:
        raise HTTPException(503, str(e)) from e
    return CardAddOut(card=srs.card_out(card, scheduler=await srs.scheduler_for(session, user.id)), created=created)


@router.post("/cards/{card_id}/review", response_model=CardOut)
async def review(card_id: int, body: ReviewCreate, session: SessionDep, user: CurrentUser) -> CardOut:
    row = await get_owned(session, VocabCard, card_id, user, "Thẻ từ")
    scheduler = await srs.scheduler_for(session, user.id)
    await srs.review(session, row, body.rating, scheduler)
    await session.commit()
    return srs.card_out(row, scheduler=scheduler)


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(card_id: int, session: SessionDep, user: CurrentUser) -> Response:
    row = await get_owned(session, VocabCard, card_id, user, "Thẻ từ")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/cards/{card_id}/audio", response_class=Response)
async def card_audio(
    card_id: int,
    session: SessionDep,
    user: CurrentUser,
    source: str | None = Query(None, pattern="^(auto|google|dictionary|kokoro)$"),
) -> Response:
    """The word's audio for listening questions (the word itself is not in the question)."""
    row = await get_owned(session, VocabCard, card_id, user, "Thẻ từ")
    return await word_audio(row.word, source)


# ---------- auto-graded review session ----------
@router.get("/session", response_model=SessionOut)
async def review_session_(
    session: SessionDep, user: CurrentUser, mode: SessionMode = "due", lesson_id: int | None = None
) -> SessionOut:
    lesson = None
    if mode == "lesson":
        if lesson_id is None:
            raise HTTPException(422, "Cần chọn bài học.")
        lesson = await get_owned(session, Lesson, lesson_id, user, "Bài học")
    return await review_session.build_session(session, user.id, mode, lesson)


@router.post("/answer", response_model=AnswerOut)
async def answer(body: AnswerIn, session: SessionDep, user: CurrentUser) -> AnswerOut:
    try:
        card_id = review_session.card_id_of(body.question_id)
    except quiz.BadQuestion as e:
        raise HTTPException(422, str(e)) from e
    card = await get_owned(session, VocabCard, card_id, user, "Thẻ từ")
    return await review_session.answer_card(session, card, body)
