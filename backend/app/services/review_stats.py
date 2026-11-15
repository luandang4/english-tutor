"""What the learner should review and when (plan C5): today's load, 7-day forecast, per-lesson memory.

Lesson "retention" = mean FSRS retrievability (predicted chance of recalling the word right now) over the
lesson's words that have been reviewed at least once. It decays between reviews, which is what "Nhớ 80%"
should express; words never reviewed are left out (null when none were reviewed yet).
"""

import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LessonStatus, Skill
from app.db.base import utcnow
from app.models.lesson import Lesson, LessonRecheck
from app.models.vocab import VocabCard
from app.schemas.api import ForecastDay, GrammarRecheckDue, LessonReviewStats, ReviewForecast
from app.services import recheck, srs
from app.services.review_session import lesson_keys

SECONDS_PER_CARD = 20
FORECAST_DAYS = 7


def _local_midnight(now: datetime, days_ahead: int) -> datetime:
    local = now.astimezone(srs.local_tz())
    return local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)


async def _grammar_due(session: AsyncSession, user_id: int, now: datetime) -> list[GrammarRecheckDue]:
    lessons = (
        await session.scalars(
            select(Lesson).where(
                Lesson.user_id == user_id, Lesson.skill == Skill.GRAMMAR, Lesson.completed_at.is_not(None)
            )
        )
    ).all()
    rows = await recheck.rechecks_by_lesson(session, [x.id for x in lessons])
    out = []
    for lesson in lessons:
        due = recheck.recheck_due_at(lesson, rows.get(lesson.id))
        if due is not None and due <= now:
            step = rows[lesson.id].step if lesson.id in rows else 0
            out.append(GrammarRecheckDue(lesson_id=lesson.id, title=lesson.title, step=step, due_at=due))
    return sorted(out, key=lambda g: g.due_at)


async def forecast(session: AsyncSession, user_id: int) -> ReviewForecast:
    now = utcnow()
    ends = [_local_midnight(now, i + 1) for i in range(FORECAST_DAYS)]
    dues = (
        await session.scalars(select(VocabCard.due_at).where(VocabCard.user_id == user_id, VocabCard.due_at < ends[-1]))
    ).all()
    counts = [0] * FORECAST_DAYS
    for d in dues:
        counts[next(i for i, end in enumerate(ends) if d < end)] += 1
    due_now = sum(1 for d in dues if d <= now)
    days = [
        ForecastDay(date=(ends[i] - timedelta(days=1)).date().isoformat(), count=counts[i])
        for i in range(FORECAST_DAYS)
    ]
    return ReviewForecast(
        due=due_now,
        minutes=math.ceil(due_now * SECONDS_PER_CARD / 60),
        days=days,
        grammar=await _grammar_due(session, user_id, now),
    )


def _vocab_stats(
    lesson: Lesson, cards: dict[str, VocabCard], row: LessonRecheck | None, now: datetime
) -> LessonReviewStats:
    mine = [cards[k] for k in lesson_keys(lesson) if k in cards]
    scheduler = srs.make_scheduler()
    recall = [r for r in (srs.retrievability(c, scheduler, now) for c in mine) if r is not None]
    return LessonReviewStats(
        lesson_id=lesson.id,
        cards=len(mine),
        due=sum(1 for c in mine if c.due_at <= now),
        retention=round(100 * sum(recall) / len(recall)) if recall else None,
        next_review_at=min((c.due_at for c in mine), default=None),
        last_quiz_score=row.last_score if row else None,
    )


def _grammar_stats(lesson: Lesson, row: LessonRecheck | None, now: datetime) -> LessonReviewStats:
    due = recheck.recheck_due_at(lesson, row)
    return LessonReviewStats(
        lesson_id=lesson.id,
        next_review_at=due,
        last_quiz_score=row.last_score if row else None,
        recheck_step=row.step if row else 0,
        recheck_due=due is not None and due <= now,
    )


async def lesson_stats(session: AsyncSession, user_id: int, skill: Skill | None = None) -> list[LessonReviewStats]:
    now = utcnow()
    q = select(Lesson).where(Lesson.user_id == user_id, Lesson.status.in_((LessonStatus.READY, LessonStatus.COMPLETED)))
    if skill is not None:
        q = q.where(Lesson.skill == skill)
    lessons = (await session.scalars(q)).all()
    rows = await recheck.rechecks_by_lesson(session, [x.id for x in lessons])
    cards = {c.word_key: c for c in (await session.scalars(select(VocabCard).where(VocabCard.user_id == user_id)))}
    return [
        _vocab_stats(x, cards, rows.get(x.id), now)
        if x.skill == Skill.VOCABULARY
        else _grammar_stats(x, rows.get(x.id), now)
        for x in lessons
        if x.skill in (Skill.VOCABULARY, Skill.GRAMMAR)
    ]
