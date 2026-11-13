from tests.conftest import UserClient, new_user_client


def test_api_requires_login(app_client) -> None:
    anon = UserClient()
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/api/topics").status_code == 200  # catalog is public
    for path in ("/api/lessons", "/api/vocab/stats", "/api/writing/tasks", "/api/progress", "/api/auth/me"):
        assert anon.get(path).status_code == 401, path
    assert anon.get("/api/tts", params={"text": "hi"}).status_code == 401


def test_register_login_logout(app_client) -> None:
    c = new_user_client("bob@example.com", "Bob")
    me = c.get("/api/auth/me").json()
    assert me["email"] == "bob@example.com" and me["display_name"] == "Bob"
    cookie = c.token
    assert cookie

    dup = UserClient().post(
        "/api/auth/register", json={"email": "BOB@example.com", "password": "another-pass", "display_name": "x"}
    )
    assert dup.status_code == 409  # emails are case-insensitive

    out = c.post("/api/auth/logout")
    assert out.status_code == 204 and "Max-Age=0" in out.headers["set-cookie"]  # browser cookie cleared
    assert UserClient(cookie).get("/api/auth/me").status_code == 401  # session revoked server-side

    other = UserClient()
    bad = other.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrong-password"})
    assert bad.status_code == 401
    ok = other.post("/api/auth/login", json={"email": " Bob@Example.com ", "password": "correct-horse-1"})
    assert ok.status_code == 200 and other.get("/api/auth/me").status_code == 200


def test_password_change_signs_out_other_devices(app_client) -> None:
    a = new_user_client("carol@example.com")
    b = UserClient()
    b.post("/api/auth/login", json={"email": "carol@example.com", "password": "correct-horse-1"})
    r = a.post("/api/auth/password", json={"current_password": "correct-horse-1", "new_password": "new-secret-99"})
    assert r.status_code == 204
    assert a.get("/api/auth/me").status_code == 200
    assert b.get("/api/auth/me").status_code == 401


def test_users_cannot_see_each_others_data(client, wait_for) -> None:
    topic = client.get("/api/topics?skill=vocabulary").json()[0]
    lid = client.post("/api/lessons", json={"topic_id": topic["id"]}).json()["id"]
    wait_for(f"/api/lessons/{lid}")

    eve = new_user_client("eve@example.com", "Eve")
    assert eve.get(f"/api/lessons/{lid}").status_code == 404
    assert eve.post(f"/api/lessons/{lid}/retry").status_code == 404
    assert eve.delete(f"/api/lessons/{lid}").status_code == 404
    assert eve.get("/api/lessons").json() == []
    assert eve.get("/api/vocab/stats").json()["total"] == 0
    assert eve.get("/api/progress").json()["streak_days"] == 0
    assert client.get(f"/api/lessons/{lid}").status_code == 200  # still there for the owner


def test_login_rate_limit() -> None:
    from app.services.auth import AuthError, LoginLimiter

    lim = LoginLimiter(max_failures=3, window_seconds=60)
    for _ in range(3):
        lim.check("1.2.3.4")
        lim.fail("1.2.3.4")
    try:
        lim.check("1.2.3.4")
        raise AssertionError("expected lockout")
    except AuthError as e:
        assert e.status == 429
    lim.check("5.6.7.8")  # other clients unaffected
