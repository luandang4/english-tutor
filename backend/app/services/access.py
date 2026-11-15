"""Who may use which quota-spending feature, and how much (per day and per calendar month).

A feature is usable when ALL of these hold:
1. the account is active,
2. the feature is switched on system-wide (admin kill switch, applies to admins too),
3. admins: allowed, unlimited — everyone else needs an active, unexpired subscription whose plan includes it,
4. today's usage is below the plan's daily limit,
5. this month's usage is below the plan's monthly limit (plus any bonus allowance from an admin).

Every API route / WebSocket that spends AI quota calls `ensure_feature` (and `ensure_quota` +
`record_usage` for countable actions). The frontend hides what is not allowed, but the server is the
authority: a hand-crafted request gets 403 / 429 just the same.

Viewing one's own history (old lessons, tasks, conversations) only needs `ensure_view`: an expired plan
locks the AI features but keeps past work readable.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import FEATURE_INFO, Feature
from app.db.base import utcnow
from app.models.access import AppSetting, UsageEvent
from app.models.plan import Plan, Subscription, UsageGrant
from app.models.user import User

SYSTEM_KEY = "system"
ALL_FEATURES = [f.value for f in Feature]

AccessStatus = Literal["admin", "active", "pending", "expired", "locked"]


@dataclass
class SystemSettings:
    features_enabled: dict[str, bool] = field(default_factory=lambda: dict.fromkeys(ALL_FEATURES, True))
    registration_open: bool = True
    upgrade_contact: str = ""  # shown to users who hit a limit (Zalo, email...)

    @classmethod
    def from_dict(cls, data: dict | None) -> "SystemSettings":
        """Unknown / old keys (default_features, daily_limits) are ignored."""
        s = cls()
        data = data or {}
        enabled = data.get("features_enabled", {})
        s.features_enabled.update({k: bool(v) for k, v in enabled.items() if k in ALL_FEATURES})
        s.registration_open = bool(data.get("registration_open", s.registration_open))
        s.upgrade_contact = str(data.get("upgrade_contact") or "").strip()[:300]
        return s


class AccessError(Exception):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


# ---------- system settings ----------
async def get_system(session: AsyncSession) -> SystemSettings:
    row = await session.get(AppSetting, SYSTEM_KEY)
    return SystemSettings.from_dict(row.value if row else None)


async def save_system(session: AsyncSession, settings: SystemSettings) -> SystemSettings:
    row = await session.get(AppSetting, SYSTEM_KEY)
    if row is None:
        session.add(AppSetting(key=SYSTEM_KEY, value=asdict(settings)))
    else:
        row.value = asdict(settings)
    await session.commit()
    return settings


async def registration_open(session: AsyncSession) -> bool:
    """Web sign-up is controlled by the admin switch (new accounts still wait for a plan)."""
    return (await get_system(session)).registration_open


# ---------- calendar (app timezone) ----------
def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def local_today() -> date:
    return datetime.now(_tz()).date()


def day_start(day: date | None = None) -> datetime:
    return datetime.combine(day or local_today(), time.min, tzinfo=_tz())


def month_start(day: date | None = None) -> datetime:
    return day_start((day or local_today()).replace(day=1))


def next_month_start(day: date | None = None) -> datetime:
    first = (day or local_today()).replace(day=1)
    return day_start((first + timedelta(days=32)).replace(day=1))


def month_key(day: date | None = None) -> str:
    return (day or local_today()).strftime("%Y-%m")


def day_key(day: date | None = None) -> str:
    return (day or local_today()).isoformat()


def _vn_date(moment: datetime) -> str:
    return moment.astimezone(_tz()).strftime("%d/%m/%Y")


# ---------- entitlement: the user's current plan ----------
@dataclass
class Entitlement:
    status: AccessStatus
    subscription: Subscription | None = None  # current one (or the expired one, for messages)

    @property
    def plan(self) -> Plan | None:
        return self.subscription.plan if self.subscription else None


def is_expired(sub: Subscription, now: datetime | None = None) -> bool:
    return sub.expires_at is not None and sub.expires_at <= (now or utcnow())


def status_for(user: User, latest: Subscription | None) -> AccessStatus:
    """Pure: the access status given the user's most recent subscription (already expiry-checked)."""
    if not user.is_active:
        return "locked"
    if user.is_admin:
        return "admin"
    if latest is None or latest.status == "cancelled":
        return "pending"
    return "active" if latest.status == "active" else "expired"


async def latest_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
    q = select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.id.desc()).limit(1)
    return await session.scalar(q)


async def expire_if_due(session: AsyncSession, subs: list[Subscription]) -> None:
    """Lazily mark active subscriptions past their expiry as expired."""
    now = utcnow()
    due = [s for s in subs if s.status == "active" and is_expired(s, now)]
    for sub in due:
        sub.status = "expired"
    if due:
        await session.commit()


async def entitlement(session: AsyncSession, user: User) -> Entitlement:
    latest = await latest_subscription(session, user.id)
    if latest is not None:
        await expire_if_due(session, [latest])
    status = status_for(user, latest)
    return Entitlement(status=status, subscription=latest if status != "pending" else None)


# ---------- permissions ----------
def features_for(ent: Entitlement, system: SystemSettings) -> list[str]:
    """Features usable right now (plan / admin + global switches)."""
    if ent.status == "admin":
        granted: list[str] = ALL_FEATURES
    elif ent.status == "active" and ent.plan is not None:
        granted = ent.plan.features or []
    else:
        granted = []
    return [f for f in ALL_FEATURES if f in granted and system.features_enabled.get(f, False)]


def view_features_for(ent: Entitlement) -> list[str]:
    """Features whose own history the user may still open (also after the plan expired)."""
    if ent.status == "admin":
        return list(ALL_FEATURES)
    if ent.status in ("active", "expired") and ent.plan is not None:
        return [f for f in ALL_FEATURES if f in (ent.plan.features or [])]
    return []


async def allowed_features(session: AsyncSession, user: User) -> list[str]:
    return features_for(await entitlement(session, user), await get_system(session))


async def viewable_features(session: AsyncSession, user: User) -> list[str]:
    return view_features_for(await entitlement(session, user))


def _contact(system: SystemSettings) -> str:
    if system.upgrade_contact:
        return f" Liên hệ để nâng gói: {system.upgrade_contact}"
    return " Hãy liên hệ admin."


def denial_message(ent: Entitlement, feature: str, system: SystemSettings) -> str:
    label = FEATURE_INFO[feature]["label"]
    plan = ent.plan
    if ent.status == "locked":
        return "Tài khoản đã bị khoá. Hãy liên hệ admin."
    if ent.status == "pending":
        return "Tài khoản của bạn đang chờ admin duyệt và chọn gói." + _contact(system)
    if ent.status == "expired" and plan is not None:
        when = _vn_date(ent.subscription.expires_at) if ent.subscription and ent.subscription.expires_at else ""
        return (
            f"Gói {plan.name} của bạn đã hết hạn{f' ngày {when}' if when else ''}. Các tính năng AI tạm khoá; "
            "bạn vẫn ôn từ vựng và xem lại bài cũ được." + _contact(system)
        )
    plan_name = plan.name if plan else "hiện tại"
    return f"Gói {plan_name} của bạn không bao gồm {label}." + _contact(system)


async def _check_feature(session: AsyncSession, user: User, feature: str) -> tuple[Entitlement, SystemSettings]:
    system = await get_system(session)
    ent = await entitlement(session, user)
    if ent.status == "locked":
        raise AccessError(denial_message(ent, feature, system), 403)
    if not system.features_enabled.get(feature, False):
        raise AccessError(f"Tính năng {FEATURE_INFO[feature]['label']} đang tạm tắt trên toàn hệ thống.", 403)
    if feature not in features_for(ent, system):
        raise AccessError(denial_message(ent, feature, system), 403)
    return ent, system


async def ensure_feature(session: AsyncSession, user: User, feature: str) -> None:
    await _check_feature(session, user, feature)


async def ensure_view(session: AsyncSession, user: User, feature: str) -> None:
    """Reading / deleting one's own past work: allowed with an active or expired plan that had the feature."""
    ent = await entitlement(session, user)
    if feature not in view_features_for(ent):
        raise AccessError(denial_message(ent, feature, await get_system(session)), 403)


async def has_any_feature(session: AsyncSession, user: User) -> bool:
    """Approved at some point (admin, active or expired plan): may use free helpers such as word audio."""
    return bool(view_features_for(await entitlement(session, user)))


# ---------- usage counters ----------
async def usage_since(session: AsyncSession, user_id: int, feature: str, start: datetime) -> int:
    q = select(func.coalesce(func.sum(UsageEvent.units), 0)).where(
        UsageEvent.user_id == user_id, UsageEvent.feature == feature, UsageEvent.created_at >= start
    )
    return int(await session.scalar(q) or 0)


async def usage_today(session: AsyncSession, user_id: int, feature: str) -> int:
    return await usage_since(session, user_id, feature, day_start())


async def usage_by_user(session: AsyncSession, start: datetime) -> dict[int, dict[str, int]]:
    q = (
        select(UsageEvent.user_id, UsageEvent.feature, func.sum(UsageEvent.units))
        .where(UsageEvent.created_at >= start)
        .group_by(UsageEvent.user_id, UsageEvent.feature)
    )
    out: dict[int, dict[str, int]] = {}
    for user_id, feature, units in (await session.execute(q)).all():
        out.setdefault(user_id, {})[feature] = int(units)
    return out


async def usage_today_by_user(session: AsyncSession) -> dict[int, dict[str, int]]:
    return await usage_by_user(session, day_start())


async def grants_this_month(session: AsyncSession, user_id: int | None = None) -> list[UsageGrant]:
    """Bonus allowances of the current month (month-wide ones and single days in it)."""
    q = select(UsageGrant).where(UsageGrant.period.startswith(month_key())).order_by(UsageGrant.id)
    if user_id is not None:
        q = q.where(UsageGrant.user_id == user_id)
    return list((await session.scalars(q)).all())


# ---------- quotas ----------
@dataclass
class FeatureQuota:
    feature: str
    used_today: int
    used_month: int
    daily_limit: int | None  # None = unlimited
    monthly_limit: int | None

    @property
    def daily_left(self) -> int | None:
        return None if self.daily_limit is None else max(0, self.daily_limit - self.used_today)

    @property
    def monthly_left(self) -> int | None:
        return None if self.monthly_limit is None else max(0, self.monthly_limit - self.used_month)

    @property
    def left(self) -> int | None:
        """What can still be used today: the smaller of day and month; None = unlimited."""
        values = [v for v in (self.daily_left, self.monthly_left) if v is not None]
        return min(values) if values else None


def _plan_limit(plan: Plan | None, feature: str, period: str) -> int:
    value = ((plan.limits or {}).get(feature) or {}).get(period) if plan else None
    return max(0, int(value or 0))


def build_quota(
    feature: str, plan: Plan | None, used_today: int, used_month: int, grants: list[UsageGrant], unlimited: bool
) -> FeatureQuota:
    """Pure: plan limits + this month's grants. A day grant raises that day's and that month's cap; a month
    grant raises the month's cap. 0 in the plan = unlimited (grants then change nothing)."""
    if unlimited:
        return FeatureQuota(feature, used_today, used_month, None, None)
    today, month = day_key(), month_key()
    mine = [g for g in grants if g.feature == feature]
    day_bonus = sum(g.amount for g in mine if g.period == today)
    month_bonus = sum(g.amount for g in mine if g.period.startswith(month))
    daily, monthly = _plan_limit(plan, feature, "daily"), _plan_limit(plan, feature, "monthly")
    return FeatureQuota(
        feature,
        used_today,
        used_month,
        daily + day_bonus if daily else None,
        monthly + month_bonus if monthly else None,
    )


async def quota(session: AsyncSession, user: User, feature: str, ent: Entitlement | None = None) -> FeatureQuota:
    ent = ent or await entitlement(session, user)
    return build_quota(
        feature,
        ent.plan,
        await usage_since(session, user.id, feature, day_start()),
        await usage_since(session, user.id, feature, month_start()),
        await grants_this_month(session, user.id),
        unlimited=ent.status == "admin",
    )


@dataclass
class Remaining:
    daily: int | None  # None = unlimited
    monthly: int | None


async def remaining(session: AsyncSession, user: User, feature: str) -> Remaining:
    q = await quota(session, user, feature)
    return Remaining(daily=q.daily_left, monthly=q.monthly_left)


async def remaining_today(session: AsyncSession, user: User, feature: str) -> int | None:
    """Units usable right now: min of what is left today and this month; None = unlimited."""
    return (await quota(session, user, feature)).left


async def max_session_minutes(session: AsyncSession, user: User) -> int | None:
    """The plan's cap on one conversation session; None = server default."""
    ent = await entitlement(session, user)
    return ent.plan.max_session_minutes if ent.status == "active" and ent.plan else None


def _limit_message(q: FeatureQuota, system: SystemSettings) -> str:
    """The month wins a tie: waiting for tomorrow would not help then."""
    info = FEATURE_INFO[q.feature]
    if q.monthly_left is not None and (q.daily_left is None or q.monthly_left <= q.daily_left):
        reset = next_month_start()
        return (
            f"Bạn đã dùng hết lượt {info['label']} tháng này ({q.monthly_limit} {info['unit']}). "
            f"Lượt mới mở vào ngày {reset.day}/{reset.month}." + _contact(system)
        )
    return (
        f"Bạn đã dùng hết lượt {info['label']} hôm nay ({q.daily_limit} {info['unit']}). "
        "Lượt mới mở lúc 0h ngày mai." + _contact(system)
    )


async def ensure_quota(session: AsyncSession, user: User, feature: str, units: int = 1) -> None:
    """Feature allowed AND enough left today and this month for `units`."""
    ent, system = await _check_feature(session, user, feature)
    q = await quota(session, user, feature, ent)
    if q.left is not None and q.left < units:
        raise AccessError(_limit_message(q, system), 429)


async def record_usage(session: AsyncSession, user_id: int, feature: str, units: int = 1) -> None:
    if units > 0:
        session.add(UsageEvent(user_id=user_id, feature=feature, units=units))
        await session.commit()


async def quotas_for(session: AsyncSession, user: User) -> tuple[Entitlement, list[FeatureQuota]]:
    """The user's quota for each feature they may use right now (for /me/usage)."""
    ent = await entitlement(session, user)
    features = features_for(ent, await get_system(session))
    return ent, [await quota(session, user, f, ent) for f in features]
