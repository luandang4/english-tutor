"""Dashboard aggregates: streak, per-skill progress, recent activity."""

from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import LessonStatus, Skill, SubmissionStatus
from app.db.base import utcnow
from app.models.conversation import ConversationSession
from app.models.lesson import ExerciseAttempt, Lesson
from app.models.pronunciation import PronunciationAttempt
from app.models.vocab import ReviewLog, VocabCard
from app.models.writing import WritingSubmission, WritingTask
from app.schemas.api import ActivityDay, ProgressOut, RecentItem, SkillProgress
from app.services import srs
from app.services.conversation.live import SCENARIOS

ACTIVITY_DAYS = 28


def scenario_label(key: str) -> str:
    return SCENARIOS.get(key, {}).get("label", key)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


async def _activity_dates(session: AsyncSession, since: datetime, tz: ZoneInfo, user_id: int) -> Counter[date]:
    sources = [
        select(ExerciseAttempt.created_at)
        .join(Lesson)
        .where(Lesson.user_id == user_id, ExerciseAttempt.created_at >= since),
        select(ReviewLog.reviewed_at)
        .join(VocabCard)
        .where(VocabCard.user_id == user_id, ReviewLog.reviewed_at >= since),
        select(WritingSubmission.created_at)
        .join(WritingTask)
        .where(WritingTask.user_id == user_id, WritingSubmission.created_at >= since),
        select(ConversationSession.created_at).where(
            ConversationSession.user_id == user_id,
            ConversationSession.created_at >= since,
            ConversationSession.ended_at.is_not(None),
        ),
        select(PronunciationAttempt.created_at).where(
            PronunciationAttempt.user_id == user_id, PronunciationAttempt.created_at >= since
        ),
    ]
    days: Counter[date] = Counter()
    for q in sources:
        for ts in (await session.scalars(q)).all():
            days[ts.astimezone(tz).date()] += 1
    return days


def _streak(days: Counter[date], today: date) -> int:
    day = today if days[today] else today - timedelta(days=1)
    streak = 0
    while days[day]:
        streak += 1
        day -= timedelta(days=1)
    return streak


async def build_progress(session: AsyncSession, user_id: int) -> ProgressOut:
    tz = ZoneInfo(get_settings().timezone)
    now_local = datetime.now(tz)
    today = now_local.date()
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    lessons = (await session.scalars(select(Lesson).where(Lesson.user_id == user_id))).all()
    tasks = (await session.scalars(select(WritingTask).where(WritingTask.user_id == user_id))).all()
    skills = []
    for skill in (Skill.VOCABULARY, Skill.GRAMMAR):
        mine = [x for x in lessons if x.skill == skill]
        done = [x for x in mine if x.status == LessonStatus.COMPLETED]
        skills.append(
            SkillProgress(
                skill=skill,
                completed=len(done),
                in_progress=sum(1 for x in mine if x.status == LessonStatus.READY),
                average_score=_avg([x.score for x in done if x.score is not None]),
            )
        )
    graded = [s for t in tasks for s in t.submissions if s.status == SubmissionStatus.GRADED]
    best_per_task = [
        max(s.overall_score for s in t.submissions if s.overall_score is not None)
        for t in tasks
        if any(s.overall_score is not None for s in t.submissions)
    ]
    skills.append(
        SkillProgress(
            skill=Skill.WRITING,
            completed=sum(1 for t in tasks if t.status == LessonStatus.COMPLETED),
            in_progress=sum(1 for t in tasks if t.status == LessonStatus.READY),
            average_score=_avg([float(x) for x in best_per_task]),
        )
    )

    conv_minutes, conv_count = (
        await session.execute(
            select(func.coalesce(func.sum(ConversationSession.duration_seconds), 0), func.count()).where(
                ConversationSession.user_id == user_id, ConversationSession.ended_at.is_not(None)
            )
        )
    ).one()
    pron_avg = await session.scalar(
        select(func.avg(PronunciationAttempt.pron_score)).where(PronunciationAttempt.user_id == user_id)
    )

    days = await _activity_dates(session, utcnow() - timedelta(days=366), tz, user_id)
    activity = [
        ActivityDay(date=(today - timedelta(days=i)).isoformat(), count=days[today - timedelta(days=i)])
        for i in range(ACTIVITY_DAYS - 1, -1, -1)
    ]

    recent: list[RecentItem] = []
    for x in lessons:
        if x.completed_at:
            recent.append(
                RecentItem(
                    kind=x.skill, title=x.title, score=x.score, at=x.completed_at, link=f"/{x.skill}/lessons/{x.id}"
                )
            )
    titles = {t.id: t.title for t in tasks}
    for s in graded:
        recent.append(
            RecentItem(
                kind="writing",
                title=titles.get(s.task_id, "Bài viết"),
                score=s.overall_score,
                at=s.created_at,
                link=f"/writing/tasks/{s.task_id}",
            )
        )
    convs = (
        await session.scalars(
            select(ConversationSession)
            .where(ConversationSession.user_id == user_id, ConversationSession.ended_at.is_not(None))
            .order_by(ConversationSession.id.desc())
            .limit(8)
        )
    ).all()
    for c in convs:
        recent.append(
            RecentItem(
                kind="conversation",
                title=f"{scenario_label(c.scenario)} · {max(1, round(c.duration_seconds / 60))} phút",
                score=None,
                at=c.created_at,
                link=f"/conversation/history/{c.id}",
            )
        )
    recent.sort(key=lambda r: r.at, reverse=True)

    return ProgressOut(
        streak_days=_streak(days, today),
        active_days_30=sum(1 for d in days if (today - d).days < 30),
        skills=skills,
        deck=await srs.deck_stats(session, day_start, user_id),
        writing_average=_avg([float(s.overall_score) for s in graded if s.overall_score is not None]),
        conversation_minutes=round(conv_minutes / 60),
        conversation_count=conv_count,
        pronunciation_average=round(pron_avg, 1) if pron_avg is not None else None,
        activity=activity,
        recent=recent[:10],
    )
