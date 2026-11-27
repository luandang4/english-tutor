"""A new vocabulary lesson is told to avoid words from the learner's earlier lessons, even before they reach
the deck."""

import time

from tests.conftest import UserClient, new_user_client
from tests.fake_ai import FakeAI


def _new_lesson(c: UserClient) -> dict:
    topic_id = c.get("/api/topics?skill=vocabulary").json()[0]["id"]
    r = c.post("/api/lessons", json={"topic_id": topic_id})
    assert r.status_code == 201, r.text
    for _ in range(100):
        data = c.get(f"/api/lessons/{r.json()['id']}").json()
        if data["status"] != "generating":
            return data
        time.sleep(0.05)
    raise AssertionError("lesson stayed busy")


def test_second_lesson_avoids_words_of_the_first(app_client, fake_ai: FakeAI) -> None:  # noqa: ANN001, ARG001
    c = new_user_client("variety@example.com")
    words = [w["word"] for w in _new_lesson(c)["content"]["words"]]
    assert words
    _new_lesson(c)
    prompt = fake_ai.prompts[-1]
    assert "Every word must be NEW" in prompt
    avoid_line = prompt.split("already studied them:")[1].split("\n")[0]
    assert all(w in avoid_line for w in words)
