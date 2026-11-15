"""Subscription plans: what a user may use and how much (per day / per calendar month)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, false, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime


class Plan(TimestampMixin, Base):
    """A package of features with limits. `limits` = {feature: {"daily": n, "monthly": n}}, 0 / null = unlimited."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(500), default="")
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    limits: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    max_session_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = server default
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # default expiry; null = never
    is_default_for_new: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())  # False = not offered
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Display only for now (payments later): e.g. "Miễn phí", "99.000đ / tháng".
    price_label: Mapped[str] = mapped_column(String(80), default="")
    billing_cycle: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "monthly", "yearly"...


class Subscription(TimestampMixin, Base):
    """A user's plan over a period. History is kept; at most one row per user is `active`."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index(
            "uq_subscriptions_one_active",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)  # null = never
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | expired | cancelled
    note: Mapped[str] = mapped_column(String(500), default="")
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="admin")  # admin | payment

    plan: Mapped[Plan] = relationship(lazy="joined")


class UsageGrant(TimestampMixin, Base):
    """Extra allowance for one user, on top of their plan. `period` is "YYYY-MM" (this month) or
    "YYYY-MM-DD" (that day only). Any grant also raises that month's cap, so it is never blocked by it."""

    __tablename__ = "usage_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    feature: Mapped[str] = mapped_column(String(20))
    amount: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(10), index=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
