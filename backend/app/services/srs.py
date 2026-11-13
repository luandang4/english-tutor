"""Vocabulary spaced repetition with FSRS (py-fsrs)."""

from datetime import datetime, timedelta

from fsrs import Card, Rating, Scheduler, State
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.lesson import Lesson
from app.models.vocab import ReviewLog, VocabCard
from app.schemas.api import CardOut, DeckStats

scheduler = Scheduler(enable_fuzzing=False)
MATURE_STABILITY_DAYS = 21


def _word_key(word: str) -> str:
    return " ".join(word.lower().split())


async def add_lesson_words(session: AsyncSession, lesson: Lesson) -> int:
    """Add the lesson's words to the deck (skips words already there). Returns number added."""
    words = (lesson.content or {}).get("words", [])
    keys = {_word_key(w["word"]): w for w in words if w.get("word")}
    if not keys:
        return 0
    existing = set(
        (
            await session.scalars(
                select(VocabCard.word_key).where(VocabCard.user_id == lesson.user_id, VocabCard.word_key.in_(keys))
            )
        ).all()
    )
    now = utcnow()
    added = 0
    for key, w in keys.items():
        if key in existing:
            continue
        card = Card(due=now)
        session.add(
            VocabCard(
                user_id=lesson.user_id,
                lesson_id=lesson.id,
                word_key=key,
                word=w["word"],
                ipa=w.get("ipa", ""),
                part_of_speech=w.get("part_of_speech", ""),
                meaning_vi=w.get("meaning_vi", ""),
                definition_en=w.get("definition_en", ""),
                example_en=w.get("example_en", ""),
                example_vi=w.get("example_vi", ""),
                fsrs_card=card.to_dict(),
                due_at=now,
            )
        )
        added += 1
    return added


async def lesson_words_in_deck(session: AsyncSession, lesson: Lesson) -> int:
    keys = [_word_key(w["word"]) for w in (lesson.content or {}).get("words", []) if w.get("word")]
    if not keys:
        return 0
    q = select(func.count()).where(VocabCard.user_id == lesson.user_id, VocabCard.word_key.in_(keys))
    return await session.scalar(q) or 0


def _fmt(delta: timedelta) -> str:
    s = delta.total_seconds()
    if s < 60:
        return "<1 phút"
    if s < 3600:
        return f"{round(s / 60)} phút"
    if s < 86400:
        return f"{round(s / 3600)} giờ"
    if s < 86400 * 30:
        return f"{round(s / 86400)} ngày"
    if s < 86400 * 365:
        return f"{round(s / 86400 / 30)} tháng"
    return f"{s / 86400 / 365:.1f} năm"


def card_out(row: VocabCard, now: datetime | None = None) -> CardOut:
    """Card DTO + the interval each rating button would schedule."""
    now = now or utcnow()
    intervals = {}
    for rating in Rating:
        nxt, _ = scheduler.review_card(Card.from_dict(row.fsrs_card), rating, review_datetime=now)
        intervals[str(int(rating))] = _fmt(nxt.due - now)
    out = CardOut.model_validate(row)
    out.intervals = intervals
    return out


async def review(session: AsyncSession, row: VocabCard, rating: int) -> VocabCard:
    now = utcnow()
    was_review = row.fsrs_card.get("state") == State.Review.value
    card, _ = scheduler.review_card(Card.from_dict(row.fsrs_card), Rating(rating), review_datetime=now)
    row.fsrs_card = card.to_dict()
    row.due_at = card.due
    row.reps += 1
    if rating == Rating.Again and was_review:  # forgot a learned card
        row.lapses += 1
    row.last_reviewed_at = now
    session.add(ReviewLog(card_id=row.id, rating=rating, reviewed_at=now))
    return row


async def deck_stats(session: AsyncSession, day_start: datetime, user_id: int) -> DeckStats:
    now = utcnow()
    rows = (await session.scalars(select(VocabCard).where(VocabCard.user_id == user_id))).all()
    total = len(rows)
    due = sum(1 for r in rows if r.due_at <= now)
    new = sum(1 for r in rows if r.reps == 0)
    mature = sum(
        1
        for r in rows
        if r.fsrs_card.get("state") == State.Review.value
        and (r.fsrs_card.get("stability") or 0) >= MATURE_STABILITY_DAYS
    )
    reviewed_today = await session.scalar(
        select(func.count())
        .select_from(ReviewLog)
        .join(VocabCard)
        .where(VocabCard.user_id == user_id, ReviewLog.reviewed_at >= day_start)
    )
    return DeckStats(
        total=total,
        due=due,
        new=new,
        learning=total - new - mature,
        mature=mature,
        reviewed_today=reviewed_today or 0,
    )
