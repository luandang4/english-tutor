"""Vocabulary deck & spaced-repetition reviews."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, get_owned
from app.core.config import get_settings
from app.db.base import utcnow
from app.models.vocab import VocabCard
from app.schemas.api import CardOut, DeckStats, ReviewCreate
from app.services import srs

router = APIRouter(prefix="/vocab", tags=["vocabulary"])


def local_day_start() -> datetime:
    tz = ZoneInfo(get_settings().timezone)
    return datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/stats", response_model=DeckStats)
async def stats(session: SessionDep, user: CurrentUser) -> DeckStats:
    return await srs.deck_stats(session, local_day_start(), user.id)


@router.get("/cards", response_model=list[CardOut])
async def list_cards(
    session: SessionDep, user: CurrentUser, due: bool = False, q: str = "", limit: int = 500
) -> list[CardOut]:
    now = utcnow()
    query = select(VocabCard).where(VocabCard.user_id == user.id)
    if due:
        query = query.where(VocabCard.due_at <= now).order_by(VocabCard.due_at)
    else:
        query = query.order_by(VocabCard.created_at.desc())
    if q.strip():
        query = query.where(VocabCard.word_key.contains(q.strip().lower()))
    rows = (await session.scalars(query.limit(min(limit, 1000)))).all()
    return [srs.card_out(r, now) for r in rows]


@router.post("/cards/{card_id}/review", response_model=CardOut)
async def review(card_id: int, body: ReviewCreate, session: SessionDep, user: CurrentUser) -> CardOut:
    row = await get_owned(session, VocabCard, card_id, user, "Thẻ từ")
    await srs.review(session, row, body.rating)
    await session.commit()
    return srs.card_out(row)


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(card_id: int, session: SessionDep, user: CurrentUser) -> Response:
    row = await get_owned(session, VocabCard, card_id, user, "Thẻ từ")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
