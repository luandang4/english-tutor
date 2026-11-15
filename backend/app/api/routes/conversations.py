"""History of voice conversations."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, get_owned, require_feature
from app.core.constants import Feature
from app.models.conversation import ConversationSession
from app.schemas.api import (
    ConversationDetail,
    ConversationRecapOut,
    ConversationSummary,
    LearnerMemoryOut,
    TranslateIn,
    TranslateOut,
)
from app.services.ai.client import AIUnavailableError
from app.services.conversation import memory, recap
from app.services.conversation import translate as translation

router = APIRouter(prefix="/conversations", tags=["conversation"], dependencies=[require_feature(Feature.CONVERSATION)])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(session: SessionDep, user: CurrentUser, limit: int = 30) -> list[ConversationSession]:
    q = (
        select(ConversationSession)
        .where(ConversationSession.user_id == user.id, ConversationSession.ended_at.is_not(None))
        .order_by(ConversationSession.id.desc())
        .limit(min(limit, 200))
    )
    return list((await session.scalars(q)).all())


@router.post("/translate", response_model=TranslateOut)
async def translate(body: TranslateIn, user: CurrentUser) -> TranslateOut:
    """Vietnamese for one of Emma's sentences, or one word in it (cached; not counted against the quota)."""
    try:
        translation.check_rate(user.id)
        result = await translation.translate(body.text, body.mode, body.context)
    except translation.RateLimitedError as e:
        raise HTTPException(429, str(e)) from e
    except AIUnavailableError as e:
        raise HTTPException(503, str(e)) from e
    return TranslateOut(**result.model_dump())


@router.get("/memory", response_model=LearnerMemoryOut)
async def get_memory(session: SessionDep, user: CurrentUser) -> LearnerMemoryOut:
    """What Emma remembers about the learner's mistakes and goals (shown on the account page)."""
    row = await memory.get(session, user.id)
    return LearnerMemoryOut(mistakes=row.mistakes, goals=row.goals) if row else LearnerMemoryOut()


@router.delete("/memory", status_code=status.HTTP_204_NO_CONTENT)
async def clear_memory(session: SessionDep, user: CurrentUser) -> Response:
    await memory.clear(session, user.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{conversation_id}/recap", response_model=ConversationRecapOut)
async def session_recap(conversation_id: int, session: SessionDep, user: CurrentUser) -> ConversationRecapOut:
    """End-of-session recap, generated once (one Gemini call) and then stored with the session."""
    row = await get_owned(session, ConversationSession, conversation_id, user, "Buổi hội thoại")
    if row.summary is None:
        if row.ended_at is None or not any(t.get("role") == "user" for t in row.transcript or []):
            raise HTTPException(409, "Buổi học chưa kết thúc hoặc bạn chưa nói câu nào.")
        try:
            row.summary = await recap.generate(row)
        except AIUnavailableError as e:
            raise HTTPException(503, str(e)) from e
        await memory.remember(session, user.id, row.summary)
        await session.commit()
    return ConversationRecapOut.model_validate(row.summary)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: int, session: SessionDep, user: CurrentUser) -> ConversationSession:
    return await get_owned(session, ConversationSession, conversation_id, user, "Buổi hội thoại")


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: int, session: SessionDep, user: CurrentUser) -> Response:
    row = await get_owned(session, ConversationSession, conversation_id, user, "Buổi hội thoại")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
