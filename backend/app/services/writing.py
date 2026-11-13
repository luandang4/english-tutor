"""Writing practice: AI-generated tasks and AI-graded submissions (Gemini)."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import LessonStatus, SubmissionStatus
from app.db.session import SessionLocal
from app.models.topic import Topic
from app.models.writing import WritingSubmission, WritingTask
from app.schemas.ai import WritingFeedback, WritingTaskDraft
from app.schemas.api import SubmissionOut, TopicOut, WritingTaskDetail, WritingTaskSummary
from app.services.ai.client import AIUnavailableError, get_ai
from app.services.ai.prompts import (
    TEACHER_SYSTEM,
    WRITING_GRADER_SYSTEM,
    writing_grading_prompt,
    writing_task_prompt,
)
from app.services.grading import count_words
from app.services.tasks import spawn

log = logging.getLogger(__name__)


async def create_task(session: AsyncSession, topic: Topic, level: str, user_id: int) -> WritingTask:
    task = WritingTask(
        user_id=user_id, topic_id=topic.id, level=level, status=LessonStatus.GENERATING, title=topic.title
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    spawn(generate_task(task.id), name=f"writing-task-{task.id}")
    return task


async def retry_task(session: AsyncSession, task: WritingTask) -> WritingTask:
    task.status, task.error = LessonStatus.GENERATING, None
    await session.commit()
    spawn(generate_task(task.id), name=f"writing-task-{task.id}")
    return task


async def generate_task(task_id: int) -> None:
    async with SessionLocal() as session:
        task = await session.get(WritingTask, task_id)
        if task is None:
            return
        try:
            draft, model = await get_ai().generate_json(
                models=get_settings().content_models,
                system=TEACHER_SYSTEM,
                prompt=writing_task_prompt(task.topic, task.level),
                schema=WritingTaskDraft,
            )
            task.prompt = draft.model_dump()
            task.title = draft.title or task.topic.title
            task.model = model
            task.status = LessonStatus.READY
            task.error = None
        except AIUnavailableError as e:
            task.status, task.error = LessonStatus.FAILED, str(e)
        except Exception:
            log.exception("Writing task %s generation failed", task_id)
            task.status, task.error = LessonStatus.FAILED, "Lỗi không mong muốn khi tạo đề bài."
        await session.commit()


async def submit(session: AsyncSession, task: WritingTask, text: str) -> WritingSubmission:
    sub = WritingSubmission(
        task_id=task.id, text=text.strip(), word_count=count_words(text), status=SubmissionStatus.GRADING
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    spawn(grade_submission(sub.id), name=f"writing-sub-{sub.id}")
    return sub


async def regrade(session: AsyncSession, sub: WritingSubmission) -> WritingSubmission:
    sub.status, sub.error = SubmissionStatus.GRADING, None
    await session.commit()
    spawn(grade_submission(sub.id), name=f"writing-sub-{sub.id}")
    return sub


async def grade_submission(sub_id: int) -> None:
    async with SessionLocal() as session:
        sub = await session.get(WritingSubmission, sub_id)
        if sub is None:
            return
        task = await session.get(WritingTask, sub.task_id)
        assert task is not None
        try:
            fb, model = await get_ai().generate_json(
                models=get_settings().writing_models,
                system=WRITING_GRADER_SYSTEM,
                prompt=writing_grading_prompt(task=task.prompt or {}, level=task.level, text=sub.text),
                schema=WritingFeedback,
                temperature=0.3,
            )
            # Keep only corrections we can actually locate in the text (for highlighting).
            fb.corrections = [c for c in fb.corrections if c.original and c.original in sub.text]
            if fb.criteria:
                fb.overall_score = round(sum(c.score for c in fb.criteria) / len(fb.criteria))
            sub.result = fb.model_dump()
            sub.overall_score = max(0, min(100, fb.overall_score))
            sub.model = model
            sub.status = SubmissionStatus.GRADED
            sub.error = None
            if task.status == LessonStatus.READY:
                task.status = LessonStatus.COMPLETED
        except AIUnavailableError as e:
            sub.status, sub.error = SubmissionStatus.FAILED, str(e)
        except Exception:
            log.exception("Writing submission %s grading failed", sub_id)
            sub.status, sub.error = SubmissionStatus.FAILED, "Lỗi không mong muốn khi chấm bài."
        await session.commit()


def task_summary(task: WritingTask) -> WritingTaskSummary:
    scores = [s.overall_score for s in task.submissions if s.overall_score is not None]
    return WritingTaskSummary(
        id=task.id,
        level=task.level,
        status=task.status,
        title=task.title,
        created_at=task.created_at,
        topic=TopicOut.model_validate(task.topic),
        best_score=max(scores) if scores else None,
        submission_count=len(task.submissions),
    )


def task_detail(task: WritingTask) -> WritingTaskDetail:
    return WritingTaskDetail(
        **task_summary(task).model_dump(),
        prompt=task.prompt,
        error=task.error,
        submissions=[SubmissionOut.model_validate(s) for s in task.submissions],
    )
