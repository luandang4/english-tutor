"""Admin-controlled access: per-user grants, system switches, daily limits — enforced by the API itself."""

import uuid

import pytest

from tests.conftest import ALL_FEATURES, grant_new_users, make_admin, new_user_client, set_system


def _email(name: str) -> str:
    return f"{name}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def admin(app_client):  # noqa: ANN001, ANN201, ARG001
    email = _email("admin")
    c = new_user_client(email, "Root")
    make_admin(email)
    yield c
    set_system(features_enabled=dict.fromkeys(ALL_FEATURES, True), daily_limits={}, registration_open=True)
    grant_new_users(ALL_FEATURES)


@pytest.fixture
def pending(app_client):  # noqa: ANN001, ANN201, ARG001
    grant_new_users([])  # new sign-ups wait for approval
    c = new_user_client(_email("pending"), "Newbie")
    grant_new_users(ALL_FEATURES)
    return c


def _vocab_topic(c) -> int:  # noqa: ANN001
    return c.get("/api/topics?skill=vocabulary").json()[0]["id"]


def test_pending_user_cannot_spend_quota_even_with_direct_api_calls(pending) -> None:
    me = pending.get("/api/auth/me").json()
    assert me["pending"] is True and me["features"] == []
    assert pending.post("/api/lessons", json={"topic_id": _vocab_topic(pending)}).status_code == 403
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
    assert msg["type"] == "error" and "chưa được cấp quyền" in msg["message"]


def test_admin_grants_a_single_feature(admin, pending) -> None:
    uid = pending.get("/api/auth/me").json()["id"]
    r = admin.patch(f"/api/admin/users/{uid}", json={"features": ["vocabulary"]})
    assert r.status_code == 200 and r.json()["features"] == ["vocabulary"]
    assert pending.get("/api/auth/me").json()["features"] == ["vocabulary"]
    assert pending.post("/api/lessons", json={"topic_id": _vocab_topic(pending)}).status_code == 201
    grammar = pending.get("/api/topics?skill=grammar").json()[0]["id"]
    assert pending.post("/api/lessons", json={"topic_id": grammar}).status_code == 403


def test_system_switch_blocks_everyone_including_admins(admin) -> None:
    system = admin.get("/api/admin/system").json()
    system["features_enabled"]["vocabulary"] = False
    assert admin.put("/api/admin/system", json=system).status_code == 200
    r = admin.post("/api/lessons", json={"topic_id": _vocab_topic(admin)})
    assert r.status_code == 403 and "tạm tắt" in r.json()["detail"]
    assert "vocabulary" not in admin.get("/api/auth/me").json()["features"]


def test_daily_limit(admin, wait_for) -> None:  # noqa: ARG001
    set_system(daily_limits={"vocabulary": 1})
    user = new_user_client(_email("limited"), "Limited")
    topic = _vocab_topic(user)
    assert user.post("/api/lessons", json={"topic_id": topic}).status_code == 201
    r = user.post("/api/lessons", json={"topic_id": topic})
    assert r.status_code == 429 and "giới hạn" in r.json()["detail"]
    usage = {u["feature"]: u for u in user.get("/api/auth/me/usage").json()}
    assert usage["vocabulary"]["used"] == 1 and usage["vocabulary"]["limit"] == 1
    # admins are not limited
    assert admin.post("/api/lessons", json={"topic_id": topic}).status_code == 201
    assert admin.post("/api/lessons", json={"topic_id": topic}).status_code == 201


def test_locking_a_user_signs_them_out(admin) -> None:
    email = _email("locked")
    victim = new_user_client(email, "Locked")
    uid = victim.get("/api/auth/me").json()["id"]
    assert admin.patch(f"/api/admin/users/{uid}", json={"is_active": False}).status_code == 200
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
    from tests.conftest import UserClient

    body = {"email": "late@example.com", "password": "correct-horse-1", "display_name": "Late"}
    assert UserClient().post("/api/auth/register", json=body).status_code == 403


def test_weak_password_rejected(app_client) -> None:  # noqa: ARG001
    from tests.conftest import UserClient

    body = {"email": "weak@example.com", "password": "onlyletters", "display_name": "Weak"}
    r = UserClient().post("/api/auth/register", json=body)
    assert r.status_code == 422 and "chữ số" in r.text
