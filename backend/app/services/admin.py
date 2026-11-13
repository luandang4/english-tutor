"""Admin actions: system switches / limits, and per-user grants. Routes in api/routes/admin.py."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AuthSession, User
from app.schemas.api import AdminUserOut, AdminUserPatch, SystemSettingsIO
from app.services import access


class AdminError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


async def update_system(session: AsyncSession, body: SystemSettingsIO) -> access.SystemSettings:
    return await access.save_system(session, access.SystemSettings.from_dict(body.model_dump()))


async def list_users(session: AsyncSession) -> list[AdminUserOut]:
    usage = await access.usage_today_by_user(session)
    users = (await session.scalars(select(User).order_by(User.id))).all()
    return [admin_user_out(u, usage.get(u.id, {})) for u in users]


def admin_user_out(user: User, usage: dict[str, int]) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        is_admin=user.is_admin,
        is_active=user.is_active,
        features=access.ALL_FEATURES if user.is_admin else list(user.features or []),
        usage_today=usage,
    )


async def update_user(session: AsyncSession, actor: User, target: User, patch: AdminUserPatch) -> User:
    """Grant / revoke features, lock / unlock, promote / demote. An admin cannot lock or demote themselves
    (so there is always at least one admin)."""
    if target.id == actor.id and (patch.is_active is False or patch.is_admin is False):
        raise AdminError("Bạn không thể tự khoá hoặc tự bỏ quyền admin của chính mình.")
    if patch.features is not None:
        target.features = [f for f in access.ALL_FEATURES if f in patch.features]
    if patch.is_admin is not None:
        target.is_admin = patch.is_admin
    if patch.is_active is not None:
        target.is_active = patch.is_active
        if not patch.is_active:  # sign the user out everywhere right away
            await session.execute(delete(AuthSession).where(AuthSession.user_id == target.id))
    await session.commit()
    return target
