"""Admin panel API: system switches, plans, per-user plan / bonus / status, usage report."""

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import AdminUser, SessionDep, get_or_404
from app.models.plan import Plan, UsageGrant
from app.models.user import User
from app.schemas.api import (
    AdminUserOut,
    AdminUserPatch,
    GrantIn,
    PlanIn,
    PlanOut,
    SubscriptionAssign,
    SubscriptionOut,
    SystemSettingsIO,
    UsageReport,
)
from app.services import access, admin, plans

router = APIRouter(prefix="/admin", tags=["admin"])


def _system_out(s: access.SystemSettings) -> SystemSettingsIO:
    return SystemSettingsIO(
        features_enabled=s.features_enabled, registration_open=s.registration_open, upgrade_contact=s.upgrade_contact
    )


# ---------- system ----------
@router.get("/system", response_model=SystemSettingsIO)
async def get_system(_: AdminUser, session: SessionDep) -> SystemSettingsIO:
    return _system_out(await access.get_system(session))


@router.put("/system", response_model=SystemSettingsIO)
async def put_system(body: SystemSettingsIO, _: AdminUser, session: SessionDep) -> SystemSettingsIO:
    return _system_out(await admin.update_system(session, body))


@router.get("/usage", response_model=UsageReport)
async def usage_report(_: AdminUser, session: SessionDep) -> UsageReport:
    return await admin.usage_report(session)


# ---------- plans ----------
@router.get("/plans", response_model=list[PlanOut])
async def list_plans(_: AdminUser, session: SessionDep) -> list[PlanOut]:
    counts = await plans.active_user_counts(session)
    return [plans.plan_out(p, counts.get(p.id, 0)) for p in await plans.list_plans(session)]


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(body: PlanIn, _: AdminUser, session: SessionDep) -> PlanOut:
    try:
        plan = await plans.create_plan(session, body)
    except plans.PlanError as e:
        raise HTTPException(e.status, str(e)) from e
    return plans.plan_out(plan)


@router.put("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(plan_id: int, body: PlanIn, _: AdminUser, session: SessionDep) -> PlanOut:
    plan = await get_or_404(session, Plan, plan_id, "Gói")
    try:
        plan = await plans.update_plan(session, plan, body)
    except plans.PlanError as e:
        raise HTTPException(e.status, str(e)) from e
    counts = await plans.active_user_counts(session)
    return plans.plan_out(plan, counts.get(plan.id, 0))


# ---------- users ----------
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
    return await admin.user_row(session, target)


@router.put("/users/{user_id}/subscription", response_model=AdminUserOut)
async def assign_plan(user_id: int, body: SubscriptionAssign, actor: AdminUser, session: SessionDep) -> AdminUserOut:
    """Choose the user's plan and expiry (also approves a pending account)."""
    target = await get_or_404(session, User, user_id, "Tài khoản")
    try:
        await plans.assign_plan(session, actor, target, body.plan_id, body.expires_at, body.note)
    except plans.PlanError as e:
        raise HTTPException(e.status, str(e)) from e
    return await admin.user_row(session, target)


@router.delete("/users/{user_id}/subscription", response_model=AdminUserOut)
async def cancel_plan(user_id: int, _: AdminUser, session: SessionDep) -> AdminUserOut:
    target = await get_or_404(session, User, user_id, "Tài khoản")
    await plans.cancel_plan(session, target)
    return await admin.user_row(session, target)


@router.get("/users/{user_id}/subscriptions", response_model=list[SubscriptionOut])
async def subscription_history(user_id: int, _: AdminUser, session: SessionDep) -> list[SubscriptionOut]:
    target = await get_or_404(session, User, user_id, "Tài khoản")
    return [admin.subscription_out(s) for s in await plans.history(session, target.id)]


@router.post("/users/{user_id}/grants", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def add_grant(user_id: int, body: GrantIn, actor: AdminUser, session: SessionDep) -> AdminUserOut:
    target = await get_or_404(session, User, user_id, "Tài khoản")
    await plans.add_grant(session, actor, target, body)
    return await admin.user_row(session, target)


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grant(grant_id: int, _: AdminUser, session: SessionDep) -> Response:
    await plans.delete_grant(session, await get_or_404(session, UsageGrant, grant_id, "Lượt cộng thêm"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
