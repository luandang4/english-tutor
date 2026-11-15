"""Admin actions: system switches, per-user status / plan view, usage report. Routes in api/routes/admin.py."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import FEATURE_INFO, Feature
from app.models.access import UsageEvent
from app.models.plan import Subscription, UsageGrant
from app.models.user import AuthSession, User
from app.schemas.api import (
    AdminUserOut,
    AdminUserPatch,
    FeatureTotal,
    GrantOut,
    SubscriptionOut,
    SystemSettingsIO,
    UsageReport,
)
from app.services import access, plans

AZURE_FREE_HOURS = 5.0  # Azure Speech F0: 5 audio hours / month of speech-to-text (pronunciation assessment)
SECONDS_PER_ASSESSMENT = 10  # not measured: rough length of one assessed recording / spoken turn


class AdminError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


async def update_system(session: AsyncSession, body: SystemSettingsIO) -> access.SystemSettings:
    return await access.save_system(session, access.SystemSettings.from_dict(body.model_dump()))


# ---------- users ----------
def subscription_out(sub: Subscription) -> SubscriptionOut:
    return SubscriptionOut(
        id=sub.id,
        plan_id=sub.plan_id,
        plan_code=sub.plan.code,
        plan_name=sub.plan.name,
        starts_at=sub.starts_at,
        expires_at=sub.expires_at,
        status=sub.status,
        note=sub.note,
        source=sub.source,
        created_at=sub.created_at,
    )


def admin_user_out(
    user: User,
    latest: Subscription | None,
    today: dict[str, int],
    month: dict[str, int],
    grants: list[UsageGrant],
) -> AdminUserOut:
    """Pure: build one row of the admin user list from pre-loaded data."""
    status = access.status_for(user, latest)
    ent = access.Entitlement(status=status, subscription=latest if status != "pending" else None)
    features = access.view_features_for(ent) if status != "locked" else []
    plan = ent.plan
    quotas = [
        access.build_quota(f, plan, today.get(f, 0), month.get(f, 0), grants, unlimited=user.is_admin) for f in features
    ]
    return AdminUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        is_admin=user.is_admin,
        is_active=user.is_active,
        access_status=status,
        features=features,
        subscription=subscription_out(ent.subscription) if ent.subscription else None,
        usage=[plans.feature_usage(q) for q in quotas],
        grants=[GrantOut.model_validate(g) for g in grants],
        usage_today=today,
    )


async def _latest_subscriptions(session: AsyncSession, user_ids: list[int] | None = None) -> dict[int, Subscription]:
    latest_ids = select(func.max(Subscription.id)).group_by(Subscription.user_id)
    if user_ids is not None:
        latest_ids = latest_ids.where(Subscription.user_id.in_(user_ids))
    subs = list((await session.scalars(select(Subscription).where(Subscription.id.in_(latest_ids)))).all())
    await access.expire_if_due(session, subs)
    return {s.user_id: s for s in subs}


async def _user_rows(session: AsyncSession, users: list[User]) -> list[AdminUserOut]:
    ids = [u.id for u in users]
    latest = await _latest_subscriptions(session, ids)
    today = await access.usage_by_user(session, access.day_start())
    month = await access.usage_by_user(session, access.month_start())
    grants: dict[int, list[UsageGrant]] = {}
    for g in await access.grants_this_month(session):
        grants.setdefault(g.user_id, []).append(g)
    return [
        admin_user_out(u, latest.get(u.id), today.get(u.id, {}), month.get(u.id, {}), grants.get(u.id, []))
        for u in users
    ]


async def list_users(session: AsyncSession) -> list[AdminUserOut]:
    users = list((await session.scalars(select(User).order_by(User.id))).all())
    return await _user_rows(session, users)


async def user_row(session: AsyncSession, user: User) -> AdminUserOut:
    return (await _user_rows(session, [user]))[0]


async def update_user(session: AsyncSession, actor: User, target: User, patch: AdminUserPatch) -> User:
    """Lock / unlock, promote / demote. An admin cannot lock or demote themselves (so there is always at least
    one admin)."""
    if target.id == actor.id and (patch.is_active is False or patch.is_admin is False):
        raise AdminError("Bạn không thể tự khoá hoặc tự bỏ quyền admin của chính mình.")
    if patch.is_admin is not None:
        target.is_admin = patch.is_admin
    if patch.is_active is not None:
        target.is_active = patch.is_active
        if not patch.is_active:  # sign the user out everywhere right away
            await session.execute(delete(AuthSession).where(AuthSession.user_id == target.id))
    await session.commit()
    return target


# ---------- system usage ----------
async def usage_report(session: AsyncSession) -> UsageReport:
    """Totals of the current calendar month for the whole system."""
    q = (
        select(
            UsageEvent.feature,
            func.coalesce(func.sum(UsageEvent.units), 0),
            func.count(),
            func.count(func.distinct(UsageEvent.user_id)),
        )
        .where(UsageEvent.created_at >= access.month_start())
        .group_by(UsageEvent.feature)
    )
    rows = {
        feature: (int(units), int(events), int(users)) for feature, units, events, users in await session.execute(q)
    }
    totals = [
        FeatureTotal(feature=f, units=u, events=e, users=n, **FEATURE_INFO[f])
        for f in access.ALL_FEATURES
        for u, e, n in [rows.get(f, (0, 0, 0))]
    ]
    assessments = rows.get(Feature.PRONUNCIATION, (0, 0, 0))[0]
    return UsageReport(
        month=access.month_key(),
        features=totals,
        conversation_minutes=rows.get(Feature.CONVERSATION, (0, 0, 0))[0],
        pronunciation_assessments=assessments,
        azure_free_hours=AZURE_FREE_HOURS,
        seconds_per_assessment_estimate=SECONDS_PER_ASSESSMENT,
        estimated_pronunciation_hours=round(assessments * SECONDS_PER_ASSESSMENT / 3600, 2),
    )
