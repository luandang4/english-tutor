from typing import Annotated, TypeVar

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_session
from app.models.user import User
from app.services import auth

SessionDep = Annotated[AsyncSession, Depends(get_session)]
M = TypeVar("M", bound=Base)


async def get_current_user(request: Request, session: SessionDep) -> User:
    user = await auth.user_for_token(session, request.cookies.get(get_settings().session_cookie))
    if user is None:
        raise HTTPException(status_code=401, detail="Bạn cần đăng nhập.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_or_404(session: AsyncSession, model: type[M], id_: int, what: str = "Bản ghi") -> M:
    obj = await session.get(model, id_)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{what} không tồn tại.")
    return obj


async def get_owned(session: AsyncSession, model: type[M], id_: int, user: User, what: str = "Bản ghi") -> M:
    """Like get_or_404, but another user's row is reported as missing (no existence leak)."""
    obj = await session.get(model, id_)
    if obj is None or getattr(obj, "user_id", None) != user.id:
        raise HTTPException(status_code=404, detail=f"{what} không tồn tại.")
    return obj
