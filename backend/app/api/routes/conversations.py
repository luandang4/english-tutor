"""History of voice conversations."""

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, get_owned
from app.models.conversation import ConversationSession
from app.schemas.api import ConversationDetail, ConversationSummary

router = APIRouter(prefix="/conversations", tags=["conversation"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(session: SessionDep, user: CurrentUser, limit: int = 30) -> list[ConversationSession]:
    q = (
        select(ConversationSession)
        .where(ConversationSession.user_id == user.id, ConversationSession.ended_at.is_not(None))
        .order_by(ConversationSession.id.desc())
        .limit(min(limit, 200))
    )
    return list((await session.scalars(q)).all())


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: int, session: SessionDep, user: CurrentUser) -> ConversationSession:
    return await get_owned(session, ConversationSession, conversation_id, user, "Buổi hội thoại")


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: int, session: SessionDep, user: CurrentUser) -> Response:
    row = await get_owned(session, ConversationSession, conversation_id, user, "Buổi hội thoại")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
