"""History of voice conversations."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, get_owned, require_feature
from app.core.constants import Feature
from app.models.conversation import ConversationSession
from app.schemas.api import ConversationDetail, ConversationSummary, TranslateIn, TranslateOut
from app.services.ai.client import AIUnavailableError
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


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: int, session: SessionDep, user: CurrentUser) -> ConversationSession:
    return await get_owned(session, ConversationSession, conversation_id, user, "Buổi hội thoại")


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: int, session: SessionDep, user: CurrentUser) -> Response:
    row = await get_owned(session, ConversationSession, conversation_id, user, "Buổi hội thoại")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
