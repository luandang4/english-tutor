"""Sentence translation practice: sources, rule-first grading, tries, reveal, stats, retry of missed sentences."""

import time

from tests.conftest import UserClient, new_user_client
from tests.fake_ai import FakeAI

BASE = "/api/writing/sentences"


def _wait(c: UserClient, set_id: int) -> dict:
    for _ in range(100):
        data = c.get(f"{BASE}/{set_id}").json()
        if data["status"] != "generating":
            return data
        time.sleep(0.05)
    raise AssertionError("set stayed generating")


def _new_set(c: UserClient, **body) -> dict:  # noqa: ANN003
    r = c.post(BASE, json={"level": "A2", **body})
    assert r.status_code == 201, r.text
    return _wait(c, r.json()["id"])


def _topic_id(c: UserClient) -> int:
    return c.get("/api/topics?skill=writing").json()[0]["id"]


def test_topic_set_hides_answers_and_grades_rule_first(app_client, fake_ai: FakeAI) -> None:  # noqa: ANN001, ARG001
    c = new_user_client("sentences1@example.com")
    data = _new_set(c, source="topic", topic_id=_topic_id(c))
    assert data["status"] == "ready" and len(data["items"]) == 10
    first = data["items"][0]
    assert first["vi"] and first["answers"] == [] and first["hint_vi"]  # answers hidden until done
    assert "Tôi đã làm lập trình viên" in first["vi"]

    calls = len(fake_ai.calls)
    r = c.post(f"{BASE}/{data['id']}/items/0/attempts", json={"answer": "i have been a developer for 2 years"})
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] == "correct" and r.json()["score"] == 100
    assert len(fake_ai.calls) == calls  # reference match: no AI call

    item = c.get(f"{BASE}/{data['id']}").json()["items"][0]
    assert item["done"] and item["answers"]  # answers shown once finished
    again = c.post(f"{BASE}/{data['id']}/items/0/attempts", json={"answer": "x"})
    assert again.status_code == 409


def test_ai_grading_hint_penalty_tries_and_reveal(app_client, fake_ai: FakeAI) -> None:  # noqa: ANN001, ARG001
    c = new_user_client("sentences2@example.com")
    data = _new_set(c, source="topic", custom={"title": "Phỏng vấn xin việc"})
    sid = data["id"]

    ok = c.post(
        f"{BASE}/{sid}/items/1/attempts", json={"answer": "I have worked as developer 3 years", "hint_used": True}
    )
    assert ok.json()["verdict"] == "correct" and ok.json()["score"] == 75  # 95 - hint penalty
    assert fake_ai.calls[-1] == "SentenceGrade"

    for _ in range(3):
        wrong = c.post(f"{BASE}/{sid}/items/2/attempts", json={"answer": "I am coder"})
        assert wrong.json()["verdict"] == "wrong" and wrong.json()["result"]["errors"][0]["fix"] == "have been"
    item = c.get(f"{BASE}/{sid}").json()["items"][2]
    assert item["done"] and item["tries_left"] == 0 and item["answers"]

    assert c.post(f"{BASE}/{sid}/items/3/reveal").json()["verdict"] == "revealed"
    detail = c.get(f"{BASE}/{sid}").json()
    stats = detail["stats"]
    assert stats["done"] == 3 and stats["correct"] == 1 and stats["wrong"] == 2
    assert stats["error_kinds"] == {"grammar": 3} and stats["weak_grammar"] == ["Hiện tại hoàn thành"]
    assert c.post(f"{BASE}/{sid}/items/99/attempts", json={"answer": "x"}).status_code == 409


def test_finishing_completes_and_missed_sentences_can_be_redone(app_client, fake_ai: FakeAI) -> None:  # noqa: ANN001, ARG001
    c = new_user_client("sentences3@example.com")
    sid = _new_set(c, source="topic", topic_id=_topic_id(c))["id"]
    for i in range(10):
        if i < 7:
            c.post(f"{BASE}/{sid}/items/{i}/attempts", json={"answer": f"I have been a developer for {i + 2} years."})
        else:
            c.post(f"{BASE}/{sid}/items/{i}/reveal")
    done = c.get(f"{BASE}/{sid}").json()
    assert done["status"] == "completed" and done["stats"]["score"] == 70

    calls = len(fake_ai.calls)
    retry = c.post(f"{BASE}/{sid}/redo-missed")
    assert retry.status_code == 201 and len(fake_ai.calls) == calls  # no AI for a retry set
    assert retry.json()["source"] == "retry" and len(retry.json()["items"]) == 3
    assert retry.json()["status"] == "ready"


def test_lesson_and_deck_sources(app_client, fake_ai: FakeAI) -> None:  # noqa: ANN001, ARG001
    c = new_user_client("sentences4@example.com")
    assert c.post(BASE, json={"source": "deck"}).status_code == 409  # empty deck
    assert c.post(BASE, json={"source": "lesson"}).status_code == 422  # lesson id required

    topic_id = c.get("/api/topics?skill=vocabulary").json()[0]["id"]
    lesson_id = c.post("/api/lessons", json={"topic_id": topic_id}).json()["id"]
    for _ in range(100):
        if c.get(f"/api/lessons/{lesson_id}").json()["status"] != "generating":
            break
        time.sleep(0.05)
    words = [w["word"] for w in c.get(f"/api/lessons/{lesson_id}").json()["content"]["words"]]
    data = _new_set(c, source="lesson", lesson_id=lesson_id)
    assert data["lesson_id"] == lesson_id and data["title"].startswith("Luyện câu:")
    assert all(w in fake_ai.prompts[-1] for w in words)  # the lesson's words are the targets

    other = new_user_client("sentences5@example.com")
    assert other.post(BASE, json={"source": "lesson", "lesson_id": lesson_id}).status_code == 404
    assert other.get(f"{BASE}/{data['id']}").status_code == 404
    assert c.delete(f"{BASE}/{data['id']}").status_code == 204
