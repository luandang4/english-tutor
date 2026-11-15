"""Lesson "Kiểm tra lại" state: the quiz in progress, the last result and the grammar 1-3-7-14 day schedule.

Vocabulary words are scheduled per card by FSRS (services/srs.py); grammar lessons have no cards, so a whole
lesson is re-checked 1, 3, 7 and 14 days after it was completed. A passed re-check on (or after) its due date
moves to the next step; a failed one comes back the next day.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Skill
from app.models.lesson import Lesson, LessonRecheck

RECHECK_DAYS = (1, 3, 7, 14)
PASS_SCORE = 60.0


async def get_recheck(session: AsyncSession, lesson: Lesson) -> LessonRecheck:
    """The lesson's re-check row, created (not committed) on first use."""
    row = await session.scalar(select(LessonRecheck).where(LessonRecheck.lesson_id == lesson.id))
    if row is None:
        row = LessonRecheck(lesson_id=lesson.id, step=0, runs=0, wrong_items=[], current={})
        session.add(row)
    return row


async def rechecks_by_lesson(session: AsyncSession, lesson_ids: list[int]) -> dict[int, LessonRecheck]:
    if not lesson_ids:
        return {}
    rows = await session.scalars(select(LessonRecheck).where(LessonRecheck.lesson_id.in_(lesson_ids)))
    return {r.lesson_id: r for r in rows.all()}


def recheck_due_at(lesson: Lesson, row: LessonRecheck | None) -> datetime | None:
    """When the next grammar re-check is due; None when not applicable or all steps are done."""
    if lesson.skill != Skill.GRAMMAR or lesson.completed_at is None:
        return None
    step = row.step if row else 0
    if step >= len(RECHECK_DAYS):
        return None
    if row is not None and row.due_at is not None:
        return row.due_at
    return lesson.completed_at + timedelta(days=RECHECK_DAYS[step])


def advance_schedule(lesson: Lesson, row: LessonRecheck, score: float, now: datetime) -> None:
    """After a full re-check: on schedule and passed -> next step; on schedule and failed -> again tomorrow."""
    due = recheck_due_at(lesson, row)
    if due is None or now < due:
        return  # early practice does not move the schedule
    assert lesson.completed_at is not None
    if score < PASS_SCORE:
        row.due_at = now + timedelta(days=1)
        return
    row.step += 1
    if row.step >= len(RECHECK_DAYS):
        row.due_at = None
    else:
        planned = lesson.completed_at + timedelta(days=RECHECK_DAYS[row.step])
        row.due_at = max(planned, now + timedelta(days=1))


def start_run(row: LessonRecheck, question_ids: list[str], full: bool) -> None:
    row.current = {"items": question_ids, "full": full, "answers": {}}


def record_result(row: LessonRecheck, question_id: str, result: str) -> None:
    """Keep the first answer to each question of the running quiz."""
    current: dict[str, Any] = dict(row.current or {})
    answers = dict(current.get("answers", {}))
    if question_id in current.get("items", []) and question_id not in answers:
        answers[question_id] = result
        current["answers"] = answers
        row.current = current  # reassign so SQLAlchemy persists the JSON change
