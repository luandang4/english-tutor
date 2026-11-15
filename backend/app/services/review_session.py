"""Auto-graded review sessions over the deck (plan C3 / C4).

Modes: `due` (cards due now, the default), and free practice when nothing is due: `soon` (next cards by due
date), `hard` (forgotten 4+ times or forgotten recently), `lesson` (words of one lesson), `random`.
Every answer goes through srs.record_answer, so free practice follows the same rule as quizzes: a right answer on
a card that is not due leaves its schedule alone, a wrong one counts as Again.
"""

import random
from collections.abc import Iterable
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.db.base import utcnow
from app.models.lesson import Lesson
from app.models.vocab import ReviewLog, VocabCard
from app.schemas.api import AnswerIn, AnswerOut, SessionOut
from app.services import quiz, srs

SESSION_CAP = 20  # cards per batch, then "ôn tiếp?"
PRACTICE_SIZE = 10
RECENT_AGAIN_DAYS = 14
POOL_LIMIT = 300


async def load_pools(session: AsyncSession, user_id: int, extra: Iterable[quiz.WordItem] = ()) -> quiz.Pools:
    """Distractor pools: the given words plus (a sample of) the learner's deck."""
    rows = (
        await session.execute(
            select(VocabCard.word, VocabCard.meaning_vi)
            .where(VocabCard.user_id == user_id)
            .order_by(func.random())
            .limit(POOL_LIMIT)
        )
    ).all()
    words = [i.word for i in extra] + [r.word for r in rows]
    meanings = [i.meaning for i in extra if i.meaning] + [r.meaning_vi for r in rows if r.meaning_vi]
    return quiz.Pools(meanings=meanings, words=words)


def _hard_filter(user_id: int, now: datetime):  # noqa: ANN202
    recent_again = (
        select(ReviewLog.card_id)
        .join(VocabCard)
        .where(
            VocabCard.user_id == user_id,
            ReviewLog.rating == 1,
            ReviewLog.reviewed_at >= now - timedelta(days=RECENT_AGAIN_DAYS),
        )
    )
    return or_(VocabCard.lapses >= srs.HARD_LAPSES, VocabCard.id.in_(recent_again))


def lesson_keys(lesson: Lesson) -> list[str]:
    return [srs.word_key(w["word"]) for w in (lesson.content or {}).get("words", []) if w.get("word")]


def _mode_query(user_id: int, mode: str, now: datetime, lesson: Lesson | None) -> tuple[Select, int]:
    """(query of the cards for this mode, batch size)."""
    base = select(VocabCard).where(VocabCard.user_id == user_id)
    if mode == "due":
        return base.where(VocabCard.due_at <= now).order_by(VocabCard.due_at), SESSION_CAP
    if mode == "soon":
        return base.where(VocabCard.due_at > now).order_by(VocabCard.due_at), PRACTICE_SIZE
    if mode == "hard":
        return base.where(_hard_filter(user_id, now)).order_by(VocabCard.lapses.desc()), SESSION_CAP
    if mode == "lesson":
        assert lesson is not None
        return base.where(VocabCard.word_key.in_(lesson_keys(lesson))).order_by(VocabCard.due_at), SESSION_CAP
    return base.order_by(func.random()), PRACTICE_SIZE


async def build_session(
    session: AsyncSession, user_id: int, mode: str, lesson: Lesson | None = None, rng: random.Random | None = None
) -> SessionOut:
    rng = rng or random.Random()
    now = utcnow()
    query, size = _mode_query(user_id, mode, now, lesson)
    cards = list((await session.scalars(query.limit(size))).all())
    total = await session.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    pools = await load_pools(session, user_id)
    if mode != "lesson":
        rng.shuffle(cards)
    return SessionOut(
        mode=mode,  # type: ignore[arg-type]
        questions=quiz.session_questions(cards, pools, rng),
        remaining=max(0, total - len(cards)) if mode in ("due", "hard", "lesson") else 0,
    )


def card_id_of(question_id: str) -> int:
    _, ref = quiz.parse_question_id(question_id, quiz.VOCAB_KINDS)
    if not ref.startswith("c") or not ref[1:].isdigit():
        raise quiz.BadQuestion("Câu hỏi không hợp lệ.")
    return int(ref[1:])


async def answer_card(session: AsyncSession, card: VocabCard, body: AnswerIn) -> AnswerOut:
    """Grade an answer about a deck card and update its schedule (first answer only; retries don't count)."""
    kind, _ = quiz.parse_question_id(body.question_id, quiz.VOCAB_KINDS)
    item = quiz.card_item(card)
    result, expected = quiz.grade_word(kind, item, body.answer)
    rating = srs.rating_for(result, body.hinted)
    scheduler = await srs.scheduler_for(session, card.user_id or 0)
    changed = await srs.record_answer(
        session, card, rating, scheduler=scheduler, source="review", counts=not body.requeued
    )
    await session.commit()
    return AnswerOut(
        result=result,  # type: ignore[arg-type]
        expected=expected,
        word=quiz.reveal(item),
        card_id=card.id,
        rating=int(rating) if changed else None,
        next_review_at=card.due_at,
    )
