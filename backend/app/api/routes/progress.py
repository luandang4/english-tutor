from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.api import ProgressOut
from app.services.progress import build_progress

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
async def progress(session: SessionDep, user: CurrentUser) -> ProgressOut:
    return await build_progress(session, user.id)
