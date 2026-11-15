"""Test setup: isolated SQLite DB + a fake Gemini client (no network, no quota)."""

import os
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="english-tutor-test-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp / 'test.db'}"
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ["FRONTEND_DIST"] = str(_tmp / "no-dist")
os.environ["TTS_PREFETCH"] = "false"  # no network in tests
os.environ["TTS_MODEL_PATH"] = str(_tmp / "no-model.onnx")  # skip Kokoro warm-up

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.ai.client import set_ai  # noqa: E402
from tests.fake_ai import FakeAI  # noqa: E402


@pytest.fixture(scope="session")
def fake_ai() -> FakeAI:
    ai = FakeAI()
    set_ai(ai)
    return ai


@pytest.fixture(scope="session")
def app_client(fake_ai: FakeAI) -> Iterator[TestClient]:
    """Runs the app lifespan once (migrations, seed); not logged in."""
    global _shared
    with TestClient(app) as c:
        _shared = c
        grant_new_users(TEST_PLAN)  # most tests want usable accounts; access tests change this
        new_user_client("owner@example.com", "Owner")  # the first account becomes admin: keep it out of tests
        yield c


COOKIE = "et_session"
ALL_FEATURES = ["conversation", "vocabulary", "grammar", "writing", "pronunciation"]
TEST_PLAN = "friends"  # seeded by the migration: every feature, (almost) no limits


def _db():  # noqa: ANN202
    import sqlite3

    return sqlite3.connect(_tmp / "test.db")


def set_system(**values: object) -> None:
    """Write admin system settings straight into the test DB (as an admin would via the panel)."""
    import json

    db = _db()
    row = db.execute("SELECT value FROM app_settings WHERE key = 'system'").fetchone()
    data = {**(json.loads(row[0]) if row else {}), **values}
    db.execute(
        "INSERT INTO app_settings (key, value) VALUES ('system', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (json.dumps(data),),
    )
    db.commit()
    db.close()


def make_admin(email: str) -> None:
    db = _db()
    db.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email.lower(),))
    db.commit()
    db.close()


def grant_new_users(plan_code: str | None) -> None:
    """New accounts start on this plan (None = they wait for an admin to choose one)."""
    db = _db()
    db.execute("UPDATE plans SET is_default_for_new = (code = ?)", (plan_code or "",))
    db.commit()
    db.close()


def set_plan(code: str, **values: object) -> None:
    """Change columns of a seeded plan (JSON columns as dict / list)."""
    import json

    db = _db()
    for key, value in values.items():
        stored = json.dumps(value) if isinstance(value, (dict, list)) else value
        db.execute(f"UPDATE plans SET {key} = ? WHERE code = ?", (stored, code))  # noqa: S608 (test helper)
    db.commit()
    db.close()


def expire_subscription(email: str) -> None:
    """Move the user's active subscription's expiry into the past (status stays 'active': expired lazily)."""
    db = _db()
    db.execute(
        "UPDATE subscriptions SET expires_at = '2000-01-01 00:00:00' WHERE status = 'active'"
        " AND user_id = (SELECT id FROM users WHERE email = ?)",
        (email.lower(),),
    )
    db.commit()
    db.close()


_shared: TestClient | None = None


class UserClient:
    """A browser-like client for one user. All users share the single lifespan-managed TestClient (so
    background jobs keep running between requests); each keeps its own session cookie."""

    def __init__(self, token: str | None = None) -> None:
        assert _shared is not None, "app_client fixture must run first"
        self.token = token

    def request(self, method: str, url: str, **kwargs):  # noqa: ANN003, ANN201
        _shared.cookies.clear()
        if self.token:
            _shared.cookies.set(COOKIE, self.token)
        response = _shared.request(method, url, **kwargs)
        self.token = _shared.cookies.get(COOKIE) or None
        return response

    def get(self, url: str, **kw):  # noqa: ANN003, ANN201
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw):  # noqa: ANN003, ANN201
        return self.request("POST", url, **kw)

    def patch(self, url: str, **kw):  # noqa: ANN003, ANN201
        return self.request("PATCH", url, **kw)

    def put(self, url: str, **kw):  # noqa: ANN003, ANN201
        return self.request("PUT", url, **kw)

    def delete(self, url: str, **kw):  # noqa: ANN003, ANN201
        return self.request("DELETE", url, **kw)


def new_user_client(email: str, name: str = "Learner") -> UserClient:
    c = UserClient()
    r = c.post("/api/auth/register", json={"email": email, "password": "correct-horse-1", "display_name": name})
    assert r.status_code == 201, r.text
    return c


@pytest.fixture(scope="session")
def client(app_client: TestClient) -> UserClient:
    """Logged-in client of the first registered account."""
    return new_user_client("alice@example.com", "Alice")


@pytest.fixture
def wait_for(client: UserClient) -> Callable[[str, tuple[str, ...]], dict]:
    def _wait(url: str, busy: tuple[str, ...] = ("generating", "grading")) -> dict:
        for _ in range(100):
            data = client.get(url).json()
            if data["status"] not in busy:
                return data
            time.sleep(0.05)
        raise AssertionError(f"{url} stayed busy")

    return _wait
