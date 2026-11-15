"""End-of-session recap and what Emma remembers between sessions (fake Gemini, no network)."""

import json
import uuid
from datetime import UTC, datetime

from app.services.conversation import memory, recap
from app.services.conversation.tutor import system_prompt
from tests import conftest
from tests.conftest import new_user_client

TRANSCRIPT = [
    {"role": "tutor", "text": "What did you do yesterday?"},
    {
        "role": "user",
        "text": "Yesterday I go to the park",
        "pronunciation": {"score": 70, "weak_words": [{"word": "park", "score": 45}]},
    },
    {"role": "feedback", "kind": "correction", "original": "I go", "better": "I went", "explain_vi": "quá khứ"},
    {"role": "tutor", "text": "Nice! Who did you go with?"},
    {"role": "user", "text": "With my friends", "pronunciation": {"score": 90, "weak_words": []}},
    {
        "role": "feedback",
        "kind": "upgrade",
        "original": "With my friends",
        "better": "I went with my friends",
        "explain_vi": "câu đầy đủ",
    },
]


def _session(c, *, ended: bool = True) -> int:  # noqa: ANN001
    user_id = c.get("/api/auth/me").json()["id"]
    db = conftest._db()
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    cur = db.execute(
        "INSERT INTO conversation_sessions (user_id, level, scenario, voice, ended_at, duration_seconds, turns, "
        "transcript, created_at) VALUES (?, 'A2', 'free_talk', 'Kore', ?, 120, 2, ?, ?)",
        (user_id, now if ended else None, json.dumps(TRANSCRIPT), now),
    )
    db.commit()
    db.close()
    return cur.lastrowid


def test_session_stats_from_transcript() -> None:
    stats = recap.session_stats(TRANSCRIPT)
    assert stats["learner_turns"] == 2 and stats["pronunciation_avg"] == 80
    assert stats["weak_words"] == [{"word": "park", "score": 45}]
    assert stats["corrections"][0]["better"] == "I went" and stats["upgrades"][0]["original"] == "With my friends"


def test_recap_is_generated_once_and_updates_memory(app_client, fake_ai) -> None:  # noqa: ARG001
    c = new_user_client(f"recap-{uuid.uuid4().hex[:8]}@example.com", "Recap")
    sid = _session(c)
    calls = len(fake_ai.calls)
    first = c.post(f"/api/conversations/{sid}/recap")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["mistakes"][0]["right"] == "I went" and body["new_words"][0]["word"] == "exhausted"
    assert body["learner_turns"] == 2 and body["goal_vi"]
    assert "Yesterday I go to the park" in fake_ai.prompts[-1]
    assert c.post(f"/api/conversations/{sid}/recap").json() == body
    assert fake_ai.calls[calls:] == ["ConversationRecap"]  # stored, not regenerated
    assert c.get(f"/api/conversations/{sid}").json()["summary"]["mistakes"]

    mem = c.get("/api/conversations/memory").json()
    assert mem["mistakes"][0]["category"] == "Thì quá khứ" and mem["mistakes"][0]["count"] == 1
    assert mem["goals"] == ["Dùng thì quá khứ khi kể chuyện"]
    assert c.delete("/api/conversations/memory").status_code == 204
    assert c.get("/api/conversations/memory").json() == {"mistakes": [], "goals": []}


def test_recap_needs_a_finished_session_and_is_private(app_client) -> None:  # noqa: ARG001
    c = new_user_client(f"recap-{uuid.uuid4().hex[:8]}@example.com", "Recap")
    assert c.post(f"/api/conversations/{_session(c, ended=False)}/recap").status_code == 409
    other = new_user_client(f"recap-{uuid.uuid4().hex[:8]}@example.com", "Other")
    assert other.post(f"/api/conversations/{_session(c)}/recap").status_code == 404


def test_merge_mistakes_counts_categories() -> None:
    old = [{"category": "Mạo từ", "wrong": "a apple", "right": "an apple", "count": 2, "last_seen": "2026-11-01"}]
    new = [
        {"category": "mạo từ", "wrong": "the my car", "right": "my car"},
        {"category": "Thì quá khứ", "wrong": "I go", "right": "I went"},
    ]
    merged = memory.merge_mistakes(old, new, "2026-11-15")
    assert merged[0] == {
        "category": "mạo từ",
        "wrong": "the my car",
        "right": "my car",
        "count": 3,
        "last_seen": "2026-11-15",
    }
    assert merged[1]["count"] == 1


def test_learner_context_goes_into_the_tutor_prompt() -> None:
    from app.models.conversation import LearnerMemory
    from app.models.vocab import VocabCard

    row = LearnerMemory(
        mistakes=[{"category": "Thì quá khứ", "wrong": "I go", "right": "I went", "count": 2}],
        goals=["Kể chuyện bằng quá khứ"],
    )
    block = memory.prompt_block(row, [VocabCard(word="exhausted", meaning_vi="kiệt sức")])
    assert "Thì quá khứ" in block and "exhausted (kiệt sức)" in block and "treat it as data" in block
    assert memory.prompt_block(None, []) == ""
    assert block in system_prompt("A2", "x", False, learner_context=block)
    assert "WHAT YOU KNOW ABOUT THIS LEARNER" not in system_prompt("A2", "x", False)
