"""Who may use which quota-spending feature, and how much per day.

A feature is usable when ALL of these hold:
1. the account is active,
2. the feature is switched on system-wide (admin kill switch, applies to admins too),
3. the user was granted it (admins have every feature),
4. today's usage is below the daily limit (admins are not limited).

Every API route / WebSocket that spends AI quota calls `ensure_feature` (and `ensure_quota` +
`record_usage` for countable actions). The frontend hides what is not allowed, but the server is the
authority: a hand-crafted request gets 403 / 429 just the same.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import FEATURE_INFO, Feature
from app.models.access import AppSetting, UsageEvent
from app.models.user import User

SYSTEM_KEY = "system"
ALL_FEATURES = [f.value for f in Feature]


def _default_limits() -> dict[str, int]:
    # 0 = unlimited. Conversation is in minutes, the rest in AI requests per day.
    return {"conversation": 30, "vocabulary": 15, "grammar": 15, "writing": 15, "pronunciation": 100}


@dataclass
class SystemSettings:
    features_enabled: dict[str, bool] = field(default_factory=lambda: dict.fromkeys(ALL_FEATURES, True))
    registration_open: bool = True
    default_features: list[str] = field(default_factory=list)  # granted to new accounts; [] = wait for approval
    daily_limits: dict[str, int] = field(default_factory=_default_limits)

    @classmethod
    def from_dict(cls, data: dict | None) -> "SystemSettings":
        s = cls()
        data = data or {}
        enabled = data.get("features_enabled", {})
        s.features_enabled.update({k: bool(v) for k, v in enabled.items() if k in ALL_FEATURES})
        s.registration_open = bool(data.get("registration_open", s.registration_open))
        s.default_features = [f for f in data.get("default_features", []) if f in ALL_FEATURES]
        s.daily_limits.update(
            {k: max(0, int(v)) for k, v in data.get("daily_limits", {}).items() if k in ALL_FEATURES and v is not None}
        )
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
    """Web sign-up needs both the env switch (ALLOW_REGISTRATION) and the admin switch."""
    return get_settings().allow_registration and (await get_system(session)).registration_open


# ---------- permissions ----------
def effective_features(user: User, system: SystemSettings) -> list[str]:
    if not user.is_active:
        return []
    granted = ALL_FEATURES if user.is_admin else (user.features or [])
    return [f for f in ALL_FEATURES if f in granted and system.features_enabled.get(f, False)]


async def ensure_feature(session: AsyncSession, user: User, feature: str) -> None:
    system = await get_system(session)
    if not system.features_enabled.get(feature, False):
        raise AccessError(f"Tính năng {FEATURE_INFO[feature]['label']} đang tạm tắt trên toàn hệ thống.", 403)
    if feature not in effective_features(user, system):
        raise AccessError(
            f"Tài khoản của bạn chưa được cấp quyền dùng {FEATURE_INFO[feature]['label']}. Hãy liên hệ admin.", 403
        )


async def has_any_feature(session: AsyncSession, user: User) -> bool:
    return bool(effective_features(user, await get_system(session)))


# ---------- daily usage ----------
def _today_start_utc() -> datetime:
    tz = ZoneInfo(get_settings().timezone)
    return datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz)


async def usage_today(session: AsyncSession, user_id: int, feature: str) -> int:
    q = select(func.coalesce(func.sum(UsageEvent.units), 0)).where(
        UsageEvent.user_id == user_id, UsageEvent.feature == feature, UsageEvent.created_at >= _today_start_utc()
    )
    return int(await session.scalar(q) or 0)


async def usage_today_by_user(session: AsyncSession) -> dict[int, dict[str, int]]:
    q = (
        select(UsageEvent.user_id, UsageEvent.feature, func.sum(UsageEvent.units))
        .where(UsageEvent.created_at >= _today_start_utc())
        .group_by(UsageEvent.user_id, UsageEvent.feature)
    )
    out: dict[int, dict[str, int]] = {}
    for user_id, feature, units in (await session.execute(q)).all():
        out.setdefault(user_id, {})[feature] = int(units)
    return out


async def remaining_today(session: AsyncSession, user: User, feature: str) -> int | None:
    """Units left today; None = unlimited."""
    limit = (await get_system(session)).daily_limits.get(feature, 0)
    if user.is_admin or limit <= 0:
        return None
    return max(0, limit - await usage_today(session, user.id, feature))


async def ensure_quota(session: AsyncSession, user: User, feature: str, units: int = 1) -> None:
    """Feature allowed AND enough of today's limit left for `units`."""
    await ensure_feature(session, user, feature)
    left = await remaining_today(session, user, feature)
    if left is not None and left < units:
        info = FEATURE_INFO[feature]
        limit = (await get_system(session)).daily_limits[feature]
        raise AccessError(
            f"Bạn đã dùng hết giới hạn {info['label']} hôm nay ({limit} {info['unit']}). Quay lại vào ngày mai nhé.",
            429,
        )


async def record_usage(session: AsyncSession, user_id: int, feature: str, units: int = 1) -> None:
    if units > 0:
        session.add(UsageEvent(user_id=user_id, feature=feature, units=units))
        await session.commit()
