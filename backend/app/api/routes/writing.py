"""Writing practice."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, SessionDep, get_or_404, get_owned, require_feature
from app.core.constants import Feature, LessonStatus, Skill, SubmissionStatus
from app.models.user import User
from app.models.writing import WritingSubmission, WritingTask
from app.schemas.api import (
    SubmissionCreate,
    SubmissionOut,
    WritingTaskCreate,
    WritingTaskDetail,
    WritingTaskSummary,
)
from app.services import access, topics
from app.services import writing as svc

router = APIRouter(prefix="/writing", tags=["writing"], dependencies=[require_feature(Feature.WRITING)])


async def _owned_submission(session: AsyncSession, submission_id: int, user: User) -> WritingSubmission:
    """Submissions are owned through their task."""
    sub = await get_or_404(session, WritingSubmission, submission_id, "Bài nộp")
    await get_owned(session, WritingTask, sub.task_id, user, "Bài nộp")
    return sub


@router.post("/tasks", response_model=WritingTaskDetail, status_code=status.HTTP_201_CREATED)
async def create_task(body: WritingTaskCreate, session: SessionDep, user: CurrentUser) -> WritingTaskDetail:
    await access.ensure_quota(session, user, Feature.WRITING)
    topic = await topics.topic_for_new_item(session, user.id, Skill.WRITING, body.topic_id, body.custom)
    if topic is None:
        raise HTTPException(404, "Chủ đề viết không tồn tại.")
    task = await svc.create_task(session, topic, body.level, user.id)
    await access.record_usage(session, user.id, Feature.WRITING)
    await session.refresh(task, ["submissions"])
    return svc.task_detail(task)


@router.get("/tasks", response_model=list[WritingTaskSummary])
async def list_tasks(session: SessionDep, user: CurrentUser, limit: int = 50) -> list[WritingTaskSummary]:
    rows = (
        await session.scalars(
            select(WritingTask)
            .where(WritingTask.user_id == user.id)
            .order_by(WritingTask.id.desc())
            .limit(min(limit, 200))
        )
    ).all()
    return [svc.task_summary(t) for t in rows]


@router.get("/tasks/{task_id}", response_model=WritingTaskDetail)
async def get_task(task_id: int, session: SessionDep, user: CurrentUser) -> WritingTaskDetail:
    return svc.task_detail(await get_owned(session, WritingTask, task_id, user, "Đề bài"))


@router.post("/tasks/{task_id}/retry", response_model=WritingTaskDetail)
async def retry_task(task_id: int, session: SessionDep, user: CurrentUser) -> WritingTaskDetail:
    task = await get_owned(session, WritingTask, task_id, user, "Đề bài")
    if task.status != LessonStatus.FAILED:
        raise HTTPException(409, "Chỉ tạo lại được đề bài bị lỗi.")
    await access.ensure_quota(session, user, Feature.WRITING)
    await svc.retry_task(session, task)
    await access.record_usage(session, user.id, Feature.WRITING)
    return svc.task_detail(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, session: SessionDep, user: CurrentUser) -> Response:
    task = await get_owned(session, WritingTask, task_id, user, "Đề bài")
    await session.delete(task)
    await session.flush()
    await topics.delete_custom_topic_if_unused(session, task.topic_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tasks/{task_id}/submissions", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def submit(task_id: int, body: SubmissionCreate, session: SessionDep, user: CurrentUser) -> WritingSubmission:
    task = await get_owned(session, WritingTask, task_id, user, "Đề bài")
    if task.status not in (LessonStatus.READY, LessonStatus.COMPLETED):
        raise HTTPException(409, "Đề bài chưa sẵn sàng.")
    await access.ensure_quota(session, user, Feature.WRITING)
    sub = await svc.submit(session, task, body.text)
    await access.record_usage(session, user.id, Feature.WRITING)
    return sub


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
async def get_submission(submission_id: int, session: SessionDep, user: CurrentUser) -> WritingSubmission:
    return await _owned_submission(session, submission_id, user)


@router.post("/submissions/{submission_id}/regrade", response_model=SubmissionOut)
async def regrade(submission_id: int, session: SessionDep, user: CurrentUser) -> WritingSubmission:
    sub = await _owned_submission(session, submission_id, user)
    if sub.status != SubmissionStatus.FAILED:
        raise HTTPException(409, "Chỉ chấm lại được bài bị lỗi.")
    await access.ensure_quota(session, user, Feature.WRITING)
    sub = await svc.regrade(session, sub)
    await access.record_usage(session, user.id, Feature.WRITING)
    return sub
