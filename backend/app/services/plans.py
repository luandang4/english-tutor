"""Plans, subscriptions and bonus allowances (admin side). Checks at request time live in services/access.py."""

from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import FEATURE_INFO
from app.db.base import utcnow
from app.models.plan import Plan, Subscription, UsageGrant
from app.models.user import User
from app.schemas.api import FeatureUsage, GrantIn, PlanIn, PlanOut
from app.services import access


class PlanError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


# ---------- plans ----------
def feature_usage(q: access.FeatureQuota) -> FeatureUsage:
    return FeatureUsage(
        feature=q.feature,
        used=q.used_today,
        limit=q.daily_limit,
        used_month=q.used_month,
        limit_month=q.monthly_limit,
        **FEATURE_INFO[q.feature],
    )


async def list_plans(session: AsyncSession) -> list[Plan]:
    return list((await session.scalars(select(Plan).order_by(Plan.sort_order, Plan.id))).all())


async def active_user_counts(session: AsyncSession) -> dict[int, int]:
    q = select(Subscription.plan_id, func.count()).where(Subscription.status == "active").group_by(Subscription.plan_id)
    return {plan_id: int(n) for plan_id, n in (await session.execute(q)).all()}


def plan_out(plan: Plan, active_users: int = 0) -> PlanOut:
    return PlanOut.model_validate(
        {
            **{c: getattr(plan, c) for c in PlanIn.model_fields if c not in ("features", "limits")},
            "features": [f for f in access.ALL_FEATURES if f in (plan.features or [])],
            "limits": {f: v for f, v in (plan.limits or {}).items() if f in access.ALL_FEATURES},
            "id": plan.id,
            "active_users": active_users,
        }
    )


def _apply(plan: Plan, body: PlanIn) -> None:
    data = body.model_dump(mode="json")
    data["features"] = [f for f in access.ALL_FEATURES if f in data["features"]]
    for key, value in data.items():
        setattr(plan, key, value)


async def _ensure_code_free(session: AsyncSession, code: str, plan_id: int | None = None) -> None:
    q = select(Plan.id).where(Plan.code == code)
    if plan_id is not None:
        q = q.where(Plan.id != plan_id)
    if await session.scalar(q):
        raise PlanError("Mã gói này đã tồn tại.", 409)


async def _only_one_default(session: AsyncSession, plan: Plan) -> None:
    if plan.is_default_for_new:
        await session.execute(update(Plan).where(Plan.id != plan.id).values(is_default_for_new=False))


async def create_plan(session: AsyncSession, body: PlanIn) -> Plan:
    await _ensure_code_free(session, body.code)
    plan = Plan()
    _apply(plan, body)
    session.add(plan)
    await session.flush()
    await _only_one_default(session, plan)
    await session.commit()
    return plan


async def update_plan(session: AsyncSession, plan: Plan, body: PlanIn) -> Plan:
    """Edits apply to everyone on the plan right away. Deactivating (is_active=False) only stops offering it:
    current subscribers keep it until it expires."""
    await _ensure_code_free(session, body.code, plan.id)
    _apply(plan, body)
    await _only_one_default(session, plan)
    await session.commit()
    return plan


async def default_plan_for_new(session: AsyncSession) -> Plan | None:
    return await session.scalar(select(Plan).where(Plan.is_default_for_new, Plan.is_active).limit(1))


# ---------- subscriptions ----------
def default_expiry(plan: Plan, start: datetime | None = None) -> datetime | None:
    return (start or utcnow()) + timedelta(days=plan.duration_days) if plan.duration_days else None


async def _end_current(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == "active")
        .values(status="cancelled")
    )
    await session.flush()


async def subscribe(
    session: AsyncSession,
    user: User,
    plan: Plan,
    *,
    expires_at: datetime | None,
    note: str = "",
    assigned_by: int | None = None,
    source: str = "admin",
) -> Subscription:
    """Put the user on `plan` from now on (the previous subscription ends, history is kept). Also approves a
    pending account. Does not commit."""
    if expires_at is not None and expires_at <= utcnow():
        raise PlanError("Ngày hết hạn phải ở tương lai.")
    await _end_current(session, user.id)
    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        plan=plan,
        starts_at=utcnow(),
        expires_at=expires_at,
        status="active",
        note=note.strip(),
        assigned_by=assigned_by,
        source=source,
    )
    session.add(sub)
    await session.flush()
    return sub


async def assign_plan(
    session: AsyncSession, actor: User, user: User, plan_id: int, expires_at: datetime | None, note: str
) -> Subscription:
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise PlanError("Gói không tồn tại.", 404)
    if not plan.is_active:
        raise PlanError("Gói này đã ngừng, hãy chọn gói khác.")
    sub = await subscribe(session, user, plan, expires_at=expires_at, note=note, assigned_by=actor.id)
    await session.commit()
    return sub


async def cancel_plan(session: AsyncSession, user: User) -> None:
    """Take the plan away: the account goes back to waiting for approval."""
    await _end_current(session, user.id)
    await session.commit()


async def history(session: AsyncSession, user_id: int) -> list[Subscription]:
    q = select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.id.desc())
    return list((await session.scalars(q)).all())


# ---------- bonus allowances ----------
async def add_grant(session: AsyncSession, actor: User, user: User, body: GrantIn) -> UsageGrant:
    period = access.day_key() if body.scope == "day" else access.month_key()
    grant = UsageGrant(
        user_id=user.id,
        feature=body.feature.value,
        amount=body.amount,
        period=period,
        note=body.note.strip(),
        created_by=actor.id,
    )
    session.add(grant)
    await session.commit()
    return grant


async def delete_grant(session: AsyncSession, grant: UsageGrant) -> None:
    await session.delete(grant)
    await session.commit()
