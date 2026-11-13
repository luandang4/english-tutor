"""Admin panel API: system-wide feature switches, daily limits, sign-up, and per-user access."""

from fastapi import APIRouter, HTTPException

from app.api.deps import AdminUser, SessionDep, get_or_404
from app.core.config import get_settings
from app.models.user import User
from app.schemas.api import AdminUserOut, AdminUserPatch, SystemSettingsIO, SystemSettingsOut
from app.services import access, admin

router = APIRouter(prefix="/admin", tags=["admin"])


def _system_out(s: access.SystemSettings) -> SystemSettingsOut:
    return SystemSettingsOut(
        features_enabled=s.features_enabled,
        registration_open=s.registration_open,
        default_features=s.default_features,
        daily_limits=s.daily_limits,
        registration_allowed_by_server=get_settings().allow_registration,
    )


@router.get("/system", response_model=SystemSettingsOut)
async def get_system(_: AdminUser, session: SessionDep) -> SystemSettingsOut:
    return _system_out(await access.get_system(session))


@router.put("/system", response_model=SystemSettingsOut)
async def put_system(body: SystemSettingsIO, _: AdminUser, session: SessionDep) -> SystemSettingsOut:
    return _system_out(await admin.update_system(session, body))


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(_: AdminUser, session: SessionDep) -> list[AdminUserOut]:
    return await admin.list_users(session)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def patch_user(user_id: int, body: AdminUserPatch, actor: AdminUser, session: SessionDep) -> AdminUserOut:
    target = await get_or_404(session, User, user_id, "Tài khoản")
    try:
        target = await admin.update_user(session, actor, target, body)
    except admin.AdminError as e:
        raise HTTPException(e.status, str(e)) from e
    usage = (await access.usage_today_by_user(session)).get(target.id, {})
    return admin.admin_user_out(target, usage)
