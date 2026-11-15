"""Plans and access: features per plan, daily / monthly limits, bonus allowances, expiry, admin bypass,
global switches and approval — all enforced by the API itself."""

import os
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.conftest import (
    ALL_FEATURES,
    TEST_PLAN,
    UserClient,
    expire_subscription,
    grant_new_users,
    make_admin,
    new_user_client,
    set_system,
)


def _email(name: str) -> str:
    return f"{name}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def admin(app_client):  # noqa: ANN001, ANN201, ARG001
    email = _email("admin")
    c = new_user_client(email, "Root")
    make_admin(email)
    yield c
    set_system(features_enabled=dict.fromkeys(ALL_FEATURES, True), registration_open=True, upgrade_contact="")
    grant_new_users(TEST_PLAN)


def _new_pending(email: str | None = None) -> UserClient:
    grant_new_users(None)  # new sign-ups wait for approval
    try:
        return new_user_client(email or _email("pending"), "Newbie")
    finally:
        grant_new_users(TEST_PLAN)


@pytest.fixture
def pending(app_client):  # noqa: ANN001, ANN201, ARG001
    return _new_pending()


def _vocab_topic(c) -> int:  # noqa: ANN001
    return c.get("/api/topics?skill=vocabulary").json()[0]["id"]


def _uid(c) -> int:  # noqa: ANN001
    return c.get("/api/auth/me").json()["id"]


def _plan(admin, features=ALL_FEATURES, **limits) -> dict:  # noqa: ANN001
    """Create a fresh plan; limits like vocabulary=(daily, monthly)."""
    body = {
        "code": f"t-{uuid.uuid4().hex[:8]}",
        "name": "Gói thử nghiệm",
        "features": features,
        "limits": {f: {"daily": d, "monthly": m} for f, (d, m) in limits.items()},
    }
    r = admin.post("/api/admin/plans", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _subscribe(admin, user, plan: dict, expires_at: str | None = None):  # noqa: ANN001, ANN201
    r = admin.put(f"/api/admin/users/{_uid(user)}/subscription", json={"plan_id": plan["id"], "expires_at": expires_at})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- approval ----------
def test_pending_user_cannot_spend_quota_even_with_direct_api_calls(pending) -> None:
    me = pending.get("/api/auth/me").json()
    assert me["pending"] is True and me["features"] == [] and me["access_status"] == "pending"
    assert me["plan"] is None
    r = pending.post("/api/lessons", json={"topic_id": _vocab_topic(pending)})
    assert r.status_code == 403 and "chờ admin duyệt" in r.json()["detail"]
    assert pending.get("/api/lessons?skill=grammar").status_code == 403
    assert pending.get("/api/lessons").json() == []
    assert pending.get("/api/writing/tasks").status_code == 403
    assert pending.post("/api/pronunciation/assess?reference_text=hi", content=b"\0" * 32000).status_code == 403
    assert pending.get("/api/conversations").status_code == 403
    assert pending.get("/api/tts?text=hello").status_code == 403
    assert pending.get("/api/admin/users").status_code == 403


def test_pending_user_is_rejected_by_the_conversation_websocket(pending, app_client) -> None:
    app_client.cookies.set("et_session", pending.token)
    with app_client.websocket_connect("/ws/conversation") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "error" and "chờ admin duyệt" in msg["message"]


def test_admin_approves_by_choosing_a_plan(admin, pending) -> None:
    plans = {p["code"]: p for p in admin.get("/api/admin/plans").json()}
    assert {"trial", "basic", "plus", "friends"} <= plans.keys()
    expires = (datetime.now(UTC) + timedelta(days=14)).isoformat()
    row = _subscribe(admin, pending, plans["trial"], expires)
    assert row["access_status"] == "active" and row["subscription"]["plan_code"] == "trial"
    me = pending.get("/api/auth/me").json()
    assert me["pending"] is False and me["features"] == ALL_FEATURES
    assert me["plan"]["name"] == "Dùng thử" and me["plan"]["expires_at"]
    usage = {u["feature"]: u for u in pending.get("/api/auth/me/usage").json()}
    assert usage["vocabulary"]["limit"] == 2 and usage["conversation"]["limit_month"] == 60
    assert pending.post("/api/lessons", json={"topic_id": _vocab_topic(pending)}).status_code == 201
    counts = {p["code"]: p["active_users"] for p in admin.get("/api/admin/plans").json()}
    assert counts["trial"] >= 1


def test_plan_features_decide_what_is_usable(admin, pending) -> None:
    _subscribe(admin, pending, _plan(admin, features=["vocabulary"]))
    assert pending.get("/api/auth/me").json()["features"] == ["vocabulary"]
    assert pending.post("/api/lessons", json={"topic_id": _vocab_topic(pending)}).status_code == 201
    grammar = pending.get("/api/topics?skill=grammar").json()[0]["id"]
    r = pending.post("/api/lessons", json={"topic_id": grammar})
    assert r.status_code == 403 and "không bao gồm" in r.json()["detail"]


def test_cancelling_the_plan_returns_the_account_to_pending(admin) -> None:
    user = new_user_client(_email("cancel"), "Cancel")
    r = admin.delete(f"/api/admin/users/{_uid(user)}/subscription")
    assert r.status_code == 200 and r.json()["access_status"] == "pending"
    assert user.get("/api/auth/me").json()["pending"] is True
    history = admin.get(f"/api/admin/users/{_uid(user)}/subscriptions").json()
    assert [h["status"] for h in history] == ["cancelled"]


def test_switching_plan_keeps_history_with_one_active(admin) -> None:
    user = new_user_client(_email("switch"), "Switch")
    plans = {p["code"]: p for p in admin.get("/api/admin/plans").json()}
    _subscribe(admin, user, plans["basic"])
    _subscribe(admin, user, plans["plus"])
    history = admin.get(f"/api/admin/users/{_uid(user)}/subscriptions").json()
    assert [(h["plan_code"], h["status"]) for h in history[:3]] == [
        ("plus", "active"),
        ("basic", "cancelled"),
        (TEST_PLAN, "cancelled"),
    ]


# ---------- switches and limits ----------
def test_system_switch_blocks_everyone_including_admins(admin) -> None:
    system = admin.get("/api/admin/system").json()
    system["features_enabled"]["vocabulary"] = False
    assert admin.put("/api/admin/system", json=system).status_code == 200
    r = admin.post("/api/lessons", json={"topic_id": _vocab_topic(admin)})
    assert r.status_code == 403 and "tạm tắt" in r.json()["detail"]
    assert "vocabulary" not in admin.get("/api/auth/me").json()["features"]


def test_daily_limit_with_contact_and_admin_bypass(admin) -> None:
    set_system(upgrade_contact="Zalo 0900 000 000")
    user = new_user_client(_email("daily"), "Daily")
    _subscribe(admin, user, _plan(admin, vocabulary=(1, 0)))
    topic = _vocab_topic(user)
    assert user.post("/api/lessons", json={"topic_id": topic}).status_code == 201
    r = user.post("/api/lessons", json={"topic_id": topic})
    detail = r.json()["detail"]
    assert r.status_code == 429 and "hôm nay" in detail and "0h ngày mai" in detail and "Zalo 0900" in detail
    usage = {u["feature"]: u for u in user.get("/api/auth/me/usage").json()}
    assert usage["vocabulary"]["used"] == 1 and usage["vocabulary"]["limit"] == 1
    assert usage["vocabulary"]["used_month"] == 1 and usage["vocabulary"]["limit_month"] is None
    # admins are not limited
    assert admin.post("/api/lessons", json={"topic_id": topic}).status_code == 201
    assert admin.post("/api/lessons", json={"topic_id": topic}).status_code == 201


def test_monthly_limit_and_bonus_grants(admin) -> None:
    user = new_user_client(_email("monthly"), "Monthly")
    _subscribe(admin, user, _plan(admin, vocabulary=(0, 1), grammar=(1, 5)))
    topic = _vocab_topic(user)
    assert user.post("/api/lessons", json={"topic_id": topic}).status_code == 201
    r = user.post("/api/lessons", json={"topic_id": topic})
    assert r.status_code == 429 and "tháng này" in r.json()["detail"] and "ngày 1/" in r.json()["detail"]

    # +1 for the month lifts the monthly cap
    row = admin.post(f"/api/admin/users/{_uid(user)}/grants", json={"feature": "vocabulary", "amount": 1}).json()
    assert row["grants"][0]["amount"] == 1
    assert {u["feature"]: u for u in row["usage"]}["vocabulary"]["limit_month"] == 2
    assert user.post("/api/lessons", json={"topic_id": topic}).status_code == 201
    assert user.post("/api/lessons", json={"topic_id": topic}).status_code == 429

    # a day grant lifts today's cap
    grammar = user.get("/api/topics?skill=grammar").json()[0]["id"]
    assert user.post("/api/lessons", json={"topic_id": grammar}).status_code == 201
    assert user.post("/api/lessons", json={"topic_id": grammar}).status_code == 429
    body = {"feature": "grammar", "amount": 1, "scope": "day"}
    assert admin.post(f"/api/admin/users/{_uid(user)}/grants", json=body).status_code == 201
    assert user.post("/api/lessons", json={"topic_id": grammar}).status_code == 201

    # grants can be removed
    grant_id = row["grants"][0]["id"]
    assert admin.delete(f"/api/admin/grants/{grant_id}").status_code == 204


def test_expired_plan_locks_ai_but_keeps_history(admin) -> None:
    email = _email("expired")
    user = new_user_client(email, "Expired")
    lesson = user.post("/api/lessons", json={"topic_id": _vocab_topic(user)}).json()
    expire_subscription(email)

    me = user.get("/api/auth/me").json()
    assert me["access_status"] == "expired" and me["features"] == [] and "vocabulary" in me["view_features"]
    r = user.post("/api/lessons", json={"topic_id": _vocab_topic(user)})
    assert r.status_code == 403 and "hết hạn" in r.json()["detail"]
    assert user.get("/api/lessons").status_code == 200 and user.get("/api/lessons").json()
    assert user.get(f"/api/lessons/{lesson['id']}").status_code == 200
    assert user.get("/api/writing/tasks").status_code == 200
    assert user.get("/api/conversations").status_code == 200
    assert user.post("/api/writing/tasks", json={"topic_id": 1}).status_code == 403
    assert user.get("/api/vocab/stats").status_code == 200  # vocabulary review needs no AI
    # the subscription row is marked expired lazily
    row = next(u for u in admin.get("/api/admin/users").json() if u["email"] == email)
    assert row["access_status"] == "expired" and row["subscription"]["status"] == "expired"


def test_expiry_must_be_in_the_future(admin) -> None:
    user = new_user_client(_email("past"), "Past")
    plan = admin.get("/api/admin/plans").json()[0]
    r = admin.put(
        f"/api/admin/users/{_uid(user)}/subscription",
        json={"plan_id": plan["id"], "expires_at": "2001-01-01T00:00:00Z"},
    )
    assert r.status_code == 400


# ---------- admin API ----------
def test_admin_endpoints_require_admin(client) -> None:
    uid = _uid(client)
    assert client.get("/api/admin/plans").status_code == 403
    assert client.post("/api/admin/plans", json={"code": "hack", "name": "Hack"}).status_code == 403
    assert client.put("/api/admin/plans/1", json={"code": "hack", "name": "Hack"}).status_code == 403
    assert client.put(f"/api/admin/users/{uid}/subscription", json={"plan_id": 1}).status_code == 403
    assert client.post(f"/api/admin/users/{uid}/grants", json={"feature": "writing", "amount": 99}).status_code == 403
    assert client.get(f"/api/admin/users/{uid}/subscriptions").status_code == 403
    assert client.get("/api/admin/usage").status_code == 403
    assert client.get("/api/admin/system").status_code == 403


def test_plan_validation(admin) -> None:
    bad = {"code": "neg", "name": "Âm", "limits": {"writing": {"daily": -1, "monthly": 0}}}
    assert admin.post("/api/admin/plans", json=bad).status_code == 422
    huge = {"code": "huge", "name": "To", "limits": {"writing": {"daily": 10**9, "monthly": 0}}}
    assert admin.post("/api/admin/plans", json=huge).status_code == 422
    assert admin.post("/api/admin/plans", json={"code": "trial", "name": "Trùng"}).status_code == 409
    assert admin.post("/api/admin/plans", json={"code": "Bad Code", "name": "X"}).status_code == 422


def test_admin_edits_and_deactivates_a_plan(admin) -> None:
    plan = _plan(admin, vocabulary=(3, 0))
    plan.update(name="Đổi tên", is_active=False, price_label="99.000đ / tháng", billing_cycle="monthly")
    r = admin.put(f"/api/admin/plans/{plan['id']}", json=plan)
    assert r.status_code == 200 and r.json()["name"] == "Đổi tên" and r.json()["is_active"] is False
    user = new_user_client(_email("inactive"), "Inactive")
    r = admin.put(f"/api/admin/users/{_uid(user)}/subscription", json={"plan_id": plan["id"]})
    assert r.status_code == 400 and "ngừng" in r.json()["detail"]


def test_usage_report(admin) -> None:
    admin.post("/api/lessons", json={"topic_id": _vocab_topic(admin)})
    report = admin.get("/api/admin/usage").json()
    totals = {f["feature"]: f for f in report["features"]}
    assert totals["vocabulary"]["units"] >= 1 and report["azure_free_hours"] == 5


def test_locking_a_user_signs_them_out(admin) -> None:
    email = _email("locked")
    victim = new_user_client(email, "Locked")
    uid = victim.get("/api/auth/me").json()["id"]
    r = admin.patch(f"/api/admin/users/{uid}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["access_status"] == "locked"
    assert victim.get("/api/auth/me").status_code == 401
    r = victim.post("/api/auth/login", json={"email": email, "password": "correct-horse-1"})
    assert r.status_code == 403


def test_admin_cannot_lock_or_demote_themselves(admin) -> None:
    me = admin.get("/api/auth/me").json()
    assert admin.patch(f"/api/admin/users/{me['id']}", json={"is_admin": False}).status_code == 400
    assert admin.patch(f"/api/admin/users/{me['id']}", json={"is_active": False}).status_code == 400


def test_registration_switch(admin) -> None:
    set_system(registration_open=False)
    assert admin.get("/api/meta").json()["registration_open"] is False
    body = {"email": "late@example.com", "password": "correct-horse-1", "display_name": "Late"}
    assert UserClient().post("/api/auth/register", json=body).status_code == 403


def test_weak_password_rejected(app_client) -> None:  # noqa: ARG001
    body = {"email": "weak@example.com", "password": "onlyletters", "display_name": "Weak"}
    r = UserClient().post("/api/auth/register", json=body)
    assert r.status_code == 422 and "chữ số" in r.text


# ---------- service level ----------
async def test_create_user_with_plan_code(app_client) -> None:  # noqa: ARG001
    from app.db.session import SessionLocal
    from app.services import access
    from app.services.auth import AuthError, create_user

    async with SessionLocal() as session:
        user = await create_user(
            session, email=_email("cli"), password="secret-pass-1", display_name="Cli", plan_code="trial"
        )
        ent = await access.entitlement(session, user)
        assert ent.status == "active" and ent.plan is not None and ent.plan.code == "trial"
        assert ent.subscription is not None and ent.subscription.expires_at is not None
        with pytest.raises(AuthError):
            await create_user(
                session, email=_email("cli"), password="secret-pass-1", display_name="X", plan_code="nope"
            )


async def test_session_minutes_cap(admin) -> None:
    from app.api.routes.live import _session_limits
    from app.db.session import SessionLocal
    from app.models.user import User

    user = new_user_client(_email("live"), "Live")
    plan = _plan(admin, conversation=(3, 0))
    plan["max_session_minutes"] = 5
    assert admin.put(f"/api/admin/plans/{plan['id']}", json=plan).status_code == 200
    _subscribe(admin, user, plan)
    async with SessionLocal() as session:
        orm_user = await session.get(User, _uid(user))
    assert (await _session_limits(orm_user)).max_seconds == 3 * 60  # minutes left today < per-session cap

    plan["limits"] = {"conversation": {"daily": 0, "monthly": 0}}
    admin.put(f"/api/admin/plans/{plan['id']}", json=plan)
    assert (await _session_limits(orm_user)).max_seconds == 5 * 60  # the plan's cap per session


def test_build_quota_combines_plan_and_grants() -> None:
    from app.models.plan import Plan, UsageGrant
    from app.services import access

    plan = Plan(limits={"writing": {"daily": 2, "monthly": 10}})
    grants = [
        UsageGrant(feature="writing", amount=3, period=access.day_key()),
        UsageGrant(feature="writing", amount=5, period=access.month_key()),
        UsageGrant(feature="grammar", amount=7, period=access.month_key()),
    ]
    q = access.build_quota("writing", plan, used_today=4, used_month=17, grants=grants, unlimited=False)
    assert (q.daily_limit, q.monthly_limit) == (5, 18)
    assert (q.daily_left, q.monthly_left, q.left) == (1, 1, 1)
    assert access.build_quota("writing", plan, 99, 99, [], unlimited=True).left is None
    assert access.build_quota("grammar", plan, 99, 99, grants, unlimited=False).left is None  # 0 = unlimited


# ---------- data migration ----------
def test_migration_moves_feature_grants_to_plans() -> None:
    """Upgrade an old-schema DB: users with features get "Bạn bè" without expiry, others stay pending."""
    backend = Path(__file__).resolve().parents[1]
    db_path = Path(tempfile.mkdtemp(prefix="migration-test-")) / "old.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"}

    def alembic(*args: str) -> None:
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend, env=env, check=True, capture_output=True)

    alembic("upgrade", "72678f74f8b7")
    db = sqlite3.connect(db_path)
    db.executemany(
        "INSERT INTO users (email, display_name, password_hash, is_admin, is_active, features, created_at)"
        " VALUES (?, ?, 'x', ?, 1, ?, CURRENT_TIMESTAMP)",
        [
            ("root@x.com", "Root", 1, '["conversation"]'),
            ("friend@x.com", "Friend", 0, '["vocabulary", "writing"]'),
            ("new@x.com", "New", 0, "[]"),
        ],
    )
    db.commit()
    alembic("upgrade", "head")
    rows = db.execute(
        "SELECT u.email, p.code, s.status, s.expires_at FROM subscriptions s"
        " JOIN users u ON u.id = s.user_id JOIN plans p ON p.id = s.plan_id"
    ).fetchall()
    assert rows == [("friend@x.com", "friends", "active", None)]
    assert "features" not in [c[1] for c in db.execute("PRAGMA table_info(users)")]
    assert db.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 4

    alembic("downgrade", "72678f74f8b7")
    restored = dict(db.execute("SELECT email, features FROM users").fetchall())
    assert restored["new@x.com"] == "[]" and "vocabulary" in restored["friend@x.com"]
    db.close()
