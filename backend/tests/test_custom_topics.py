"""Learner-defined topics for vocabulary / grammar lessons and writing tasks."""

from tests.conftest import new_user_client

CUSTOM = {"title": "Đi phỏng vấn ngành logistics", "request": "Tập trung từ về kho bãi và vận chuyển quốc tế"}


def test_custom_vocabulary_lesson(client, fake_ai, wait_for) -> None:
    r = client.post("/api/lessons", json={"custom": CUSTOM, "skill": "vocabulary", "level": "B1"})
    assert r.status_code == 201, r.text
    lesson = wait_for(f"/api/lessons/{r.json()['id']}")
    assert lesson["status"] == "ready" and lesson["skill"] == "vocabulary"
    assert lesson["topic"]["title_vi"] == CUSTOM["title"] and lesson["topic"]["is_custom"] is True
    prompt = next(p for p in reversed(fake_ai.prompts) if CUSTOM["title"] in p)
    assert "chosen by the learner" in prompt and CUSTOM["request"] in prompt

    # custom topics are private to the lesson: not listed with the presets
    assert all(not t["is_custom"] for t in client.get("/api/topics").json())

    # deleting the lesson removes its custom topic too
    topic_id = lesson["topic"]["id"]
    assert client.delete(f"/api/lessons/{lesson['id']}").status_code == 204
    r = client.post("/api/lessons", json={"topic_id": topic_id, "level": "B1"})
    assert r.status_code == 404


def test_custom_grammar_lesson_without_request(client, wait_for) -> None:
    body = {"custom": {"title": "Câu điều kiện trong email công việc"}, "skill": "grammar", "level": "B2"}
    lesson = wait_for(f"/api/lessons/{client.post('/api/lessons', json=body).json()['id']}")
    assert lesson["status"] == "ready" and lesson["skill"] == "grammar"


def test_custom_writing_task(client, wait_for) -> None:
    r = client.post("/api/writing/tasks", json={"custom": CUSTOM, "level": "B1"})
    assert r.status_code == 201, r.text
    task = wait_for(f"/api/writing/tasks/{r.json()['id']}")
    assert task["status"] == "ready" and task["topic"]["is_custom"] is True


def test_custom_topic_validation(client) -> None:
    both = {"topic_id": 1, "custom": CUSTOM, "skill": "vocabulary"}
    assert client.post("/api/lessons", json=both).status_code == 422
    assert client.post("/api/lessons", json={"level": "B1"}).status_code == 422
    assert client.post("/api/lessons", json={"custom": CUSTOM}).status_code == 422  # skill required
    assert client.post("/api/lessons", json={"custom": {"title": "x"}, "skill": "grammar"}).status_code == 422


def test_custom_topic_of_another_user_is_not_reusable(client, wait_for) -> None:
    lesson = client.post("/api/lessons", json={"custom": CUSTOM, "skill": "vocabulary"}).json()
    topic_id = wait_for(f"/api/lessons/{lesson['id']}")["topic"]["id"]
    bob = new_user_client("bob-custom@example.com", "Bob")
    assert bob.post("/api/lessons", json={"topic_id": topic_id}).status_code == 404
