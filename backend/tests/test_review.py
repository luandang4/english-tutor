"""Review & spaced repetition: lesson re-check quizzes, auto-graded sessions, scheduling rules, adding words."""

import json
import random
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fsrs import Rating
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.lesson import Lesson, LessonRecheck
from app.services import grading, quiz, recheck, srs
from tests import conftest
from tests.conftest import new_user_client, set_plan
from tests.fake_ai import MEANINGS


def _user(name: str = "learner"):  # noqa: ANN202
    return new_user_client(f"{name}-{uuid.uuid4().hex[:8]}@example.com", name.title())


def _sql(query: str, params: tuple = ()) -> None:
    db = sqlite3.connect(conftest._tmp / "test.db")
    db.execute(query, params)
    db.commit()
    db.close()


def _db_time(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(tzinfo=None).isoformat(sep=" ")


def _make_due(card_id: int) -> None:
    _sql("UPDATE vocab_cards SET due_at = ? WHERE id = ?", (_db_time(datetime.now(UTC) - timedelta(hours=1)), card_id))


def _lesson(c, skill: str) -> dict:  # noqa: ANN001
    topic = c.get(f"/api/topics?skill={skill}").json()[0]["id"]
    lid = c.post("/api/lessons", json={"topic_id": topic}).json()["id"]
    for _ in range(200):
        data = c.get(f"/api/lessons/{lid}").json()
        if data["status"] != "generating":
            return data
    raise AssertionError("lesson stayed generating")


def _complete(c, lesson: dict, wrong_first: str | None = None) -> None:  # noqa: ANN001
    answers = {"multiple_choice": "a travel plan", "fill_blank": "souvenir", "produce": "My boarding pass, please."}
    for ex in lesson["exercises"]:
        url = f"/api/lessons/{lesson['id']}/exercises/{ex['id']}/attempts"
        if ex["type"] == wrong_first:
            c.post(url, json={"answer": "nope"})
        c.post(url, json={"answer": answers[ex["type"]]})


def _right_answer(q: dict) -> str:
    """What a learner who knows the fake lesson would answer."""
    word = next(w for w in MEANINGS if f"w{list(MEANINGS).index(w)}" == q["id"].split(":")[1])
    return {
        "choose_meaning": MEANINGS[word],
        "fill_sentence": word,
    }.get(q["kind"], word)


def _add(c, word: str, **extra) -> dict:  # noqa: ANN001, ANN003
    body = {"word": word, "meaning_vi": f"nghĩa {uuid.uuid4().hex[:4]}", "example_en": f"I like the {word}.", **extra}
    r = c.post("/api/vocab/cards", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- pure rules ----------
@pytest.mark.parametrize(
    ("answer", "expected", "result"),
    [
        ("  Souvenir! ", "souvenir", "correct"),
        ("boarding-pass", "boarding pass", "correct"),
        ("Itinerery", "itinerary", "near"),  # one letter off on a long word
        ("itinry", "itinerary", "wrong"),
        ("cot", "cat", "wrong"),  # short words must be exact
        ("", "cat", "wrong"),
    ],
)
def test_typed_answers_are_tolerant(answer: str, expected: str, result: str) -> None:
    assert grading.check_typed(answer, [expected]) == result


def test_fill_sentence_blanks_inflected_forms() -> None:
    assert quiz.blank_sentence("She bought two souvenirs.", "souvenir") == ("She bought two ___.", "souvenirs")
    assert quiz.blank_sentence("We stopped early.", "stop") == ("We ___ early.", "stopped")
    assert quiz.blank_sentence("Show your Boarding Pass now", "boarding pass") == ("Show your ___ now", "Boarding Pass")
    assert quiz.blank_sentence("He gave up smoking.", "give up") is None  # irregular: another question type
    assert quiz.blank_sentence("A catalogue of cats.", "cat") == ("A catalogue of ___.", "cats")


def test_rating_mapping() -> None:
    assert srs.rating_for("correct") == Rating.Good
    assert srs.rating_for("correct", hinted=True) == Rating.Hard
    assert srs.rating_for("near") == Rating.Hard
    assert srs.rating_for("wrong", hinted=True) == Rating.Again


def test_new_card_daily_cap() -> None:
    assert srs.intro_offsets({}, 3, cap=20) == [1, 1, 1]  # first review ~1 day after learning
    assert srs.intro_offsets({1: 19}, 3, cap=20) == [1, 2, 2]
    assert srs.intro_offsets({1: 2, 2: 2}, 3, cap=2) == [3, 3, 4]


def test_grammar_recheck_schedule() -> None:
    done = datetime(2026, 1, 1, tzinfo=UTC)
    lesson = Lesson(id=1, skill="grammar", completed_at=done)
    row = LessonRecheck(lesson_id=1, step=0, due_at=None)
    assert recheck.recheck_due_at(lesson, None) == done + timedelta(days=1)
    recheck.advance_schedule(lesson, row, 100, done + timedelta(hours=5))  # early practice
    assert row.step == 0 and recheck.recheck_due_at(lesson, row) == done + timedelta(days=1)
    recheck.advance_schedule(lesson, row, 40, done + timedelta(days=1))  # failed on time: again tomorrow
    assert row.step == 0 and row.due_at == done + timedelta(days=2)
    recheck.advance_schedule(lesson, row, 90, done + timedelta(days=2))
    assert row.step == 1 and row.due_at == done + timedelta(days=3)
    for day in (3, 7, 14):
        recheck.advance_schedule(lesson, row, 90, done + timedelta(days=day))
    assert row.step == 4 and recheck.recheck_due_at(lesson, row) is None


def test_lesson_quiz_questions_vary_and_fall_back() -> None:
    items = [
        quiz.WordItem(
            ref=f"w{i}", data={"word": w, "meaning_vi": m, "example_en": f"An example with {w}."}, audio_url=""
        )
        for i, (w, m) in enumerate(MEANINGS.items())
    ]
    pools = quiz.Pools(meanings=list(MEANINGS.values()), words=list(MEANINGS))
    qs = quiz.lesson_word_questions(items, pools, random.Random(1))
    assert len(qs) == 6  # small lesson: every word twice, never the same kind twice
    assert len({q.id for q in qs}) == 6


# ---------- lesson "Kiểm tra lại" ----------
def test_vocab_lesson_quiz_hides_answers_and_grades(app_client) -> None:  # noqa: ARG001
    c = _user()
    lesson = _lesson(c, "vocabulary")
    quiz_out = c.post(f"/api/lessons/{lesson['id']}/quiz").json()  # any time, even before finishing the lesson
    qs = quiz_out["questions"]
    assert len(qs) == 6 and {q["kind"] for q in qs} <= set(quiz.LESSON_QUIZ_KINDS)
    for q in qs:
        assert "answer" not in json.dumps(q).lower().replace("audio_url", "")
        if q["kind"] in ("listen_type", "vi_to_en", "fill_sentence"):
            word = _right_answer(q)
            assert word not in json.dumps(q, ensure_ascii=False).lower(), q
        if q["audio_url"]:
            assert q["audio_url"].startswith(f"/api/lessons/{lesson['id']}/words/")

    first, second, *rest = qs
    ok = c.post(
        f"/api/lessons/{lesson['id']}/quiz/answer", json={"question_id": first["id"], "answer": _right_answer(first)}
    )
    assert ok.json()["result"] == "correct" and ok.json()["rating"] is None  # words not in the deck yet
    bad = c.post(f"/api/lessons/{lesson['id']}/quiz/answer", json={"question_id": second["id"], "answer": "zzz"}).json()
    assert bad["result"] == "wrong" and bad["expected"] and bad["word"]["word"] in MEANINGS
    # a second answer to the same question does not replace the first
    c.post(
        f"/api/lessons/{lesson['id']}/quiz/answer", json={"question_id": second["id"], "answer": _right_answer(second)}
    )
    for q in rest:
        c.post(f"/api/lessons/{lesson['id']}/quiz/answer", json={"question_id": q["id"], "answer": _right_answer(q)})

    result = c.post(f"/api/lessons/{lesson['id']}/quiz/finish").json()
    assert result["total"] == 6 and result["wrong"] == 1 and result["score"] == round(500 / 6, 1)
    missed = next(i for i in result["items"] if i["result"] == "wrong")["label"]

    retry = c.post(f"/api/lessons/{lesson['id']}/quiz?only_wrong=true").json()["questions"]
    assert retry and all(_right_answer(q) in (missed, MEANINGS[missed]) for q in retry)
    stats = next(s for s in c.get("/api/vocab/lesson-stats").json() if s["lesson_id"] == lesson["id"])
    assert stats["last_quiz_score"] == result["score"]


def test_quiz_answers_on_deck_words_follow_the_schedule_rule(app_client) -> None:  # noqa: ARG001
    c = _user()
    lesson = _lesson(c, "vocabulary")
    _complete(c, lesson)
    q = next(q for q in c.post(f"/api/lessons/{lesson['id']}/quiz").json()["questions"] if q["kind"] != "fill_sentence")
    out = c.post(
        f"/api/lessons/{lesson['id']}/quiz/answer", json={"question_id": q["id"], "answer": _right_answer(q)}
    ).json()
    assert out["card_id"] and out["rating"] is None  # learned today, not due: right answer keeps the schedule
    q2 = next(x for x in c.post(f"/api/lessons/{lesson['id']}/quiz").json()["questions"] if x["id"] != q["id"])
    out2 = c.post(f"/api/lessons/{lesson['id']}/quiz/answer", json={"question_id": q2["id"], "answer": "zzz"}).json()
    assert out2["rating"] == 1  # wrong counts as Again even when not due


def test_grammar_recheck_flow(app_client) -> None:  # noqa: ARG001
    c = _user()
    lesson = _lesson(c, "grammar")
    _complete(c, lesson, wrong_first="fill_blank")
    qs = c.post(f"/api/lessons/{lesson['id']}/quiz").json()["questions"]
    assert [q["kind"] for q in qs] == ["grammar_fill", "grammar_choice"]  # missed exercise comes first
    assert all("souvenir" not in json.dumps(q) for q in qs)

    def run(answers: dict[str, str]) -> dict:
        for q in c.post(f"/api/lessons/{lesson['id']}/quiz").json()["questions"]:
            c.post(
                f"/api/lessons/{lesson['id']}/quiz/answer", json={"question_id": q["id"], "answer": answers[q["kind"]]}
            )
        return c.post(f"/api/lessons/{lesson['id']}/quiz/finish").json()

    right = {"grammar_fill": "Souvenir.", "grammar_choice": "a travel plan"}
    early = run(right)
    assert early["score"] == 100 and early["recheck_step"] == 0  # practice before the due date: no step
    assert not any(g["lesson_id"] == lesson["id"] for g in c.get("/api/vocab/forecast").json()["grammar"])

    done = datetime.now(UTC) - timedelta(days=2)
    _sql("UPDATE lessons SET completed_at = ? WHERE id = ?", (_db_time(done), lesson["id"]))
    assert any(g["lesson_id"] == lesson["id"] for g in c.get("/api/vocab/forecast").json()["grammar"])
    failed = run({"grammar_fill": "x", "grammar_choice": "x"})
    assert failed["recheck_step"] == 0 and failed["wrong"] == 2
    _sql("UPDATE lesson_rechecks SET due_at = NULL WHERE lesson_id = ?", (lesson["id"],))
    passed = run(right)
    assert passed["recheck_step"] == 1
    assert passed["next_recheck_at"][:10] == (done + timedelta(days=3)).date().isoformat()


# ---------- review sessions ----------
def test_session_scheduling_rule_and_retries(app_client) -> None:  # noqa: ARG001
    c = _user()
    card = _add(c, "lantern")["card"]
    assert c.get("/api/vocab/session").json()["questions"] == []  # nothing due on day 0
    assert c.get("/api/vocab/due-count").json() == {"due": 0}

    q = c.get("/api/vocab/session?mode=random").json()["questions"][0]
    assert q["card_id"] == card["id"] and q["kind"] in quiz.STAGE_KINDS["new"] + quiz.FALLBACK
    answer = card["meaning_vi"] if q["kind"] == "choose_meaning" else "lantern"
    early = c.post("/api/vocab/answer", json={"question_id": q["id"], "answer": answer}).json()
    assert early["result"] == "correct" and early["rating"] is None and early["next_review_at"] == card["due_at"]

    _make_due(card["id"])
    assert c.get("/api/vocab/due-count").json() == {"due": 1}
    due_q = c.get("/api/vocab/session").json()["questions"][0]
    wrong = c.post("/api/vocab/answer", json={"question_id": due_q["id"], "answer": "zzz"}).json()
    assert wrong["rating"] == 1 and wrong["expected"]
    retry = c.post("/api/vocab/answer", json={"question_id": due_q["id"], "answer": "zzz", "requeued": True}).json()
    assert retry["rating"] is None  # only the first answer in a session counts

    _make_due(card["id"])
    vi = f"vi_to_en:c{card['id']}"
    hinted = c.post("/api/vocab/answer", json={"question_id": vi, "answer": "lanturn", "hinted": True}).json()
    assert hinted["result"] == "near" and hinted["rating"] == 2


def test_free_practice_modes(app_client) -> None:  # noqa: ARG001
    c = _user()
    ids = [_add(c, w)["card"]["id"] for w in ("anchor", "harbor", "compass")]
    soon = c.get("/api/vocab/session?mode=soon").json()
    assert {q["card_id"] for q in soon["questions"]} == set(ids)
    _sql("UPDATE vocab_cards SET lapses = 5 WHERE id = ?", (ids[0],))
    hard = c.get("/api/vocab/session?mode=hard").json()["questions"]
    assert [q["card_id"] for q in hard] == [ids[0]]
    cards = {x["id"]: x for x in c.get("/api/vocab/cards").json()}
    assert cards[ids[0]]["is_hard"] and not cards[ids[1]]["is_hard"]
    assert c.get("/api/vocab/stats").json()["hard"] == 1
    assert c.get("/api/vocab/session?mode=lesson").status_code == 422


def test_new_cards_per_day_cap_spreads_first_reviews(app_client) -> None:  # noqa: ARG001
    c = _user()
    assert c.get("/api/vocab/settings").json() == {"desired_retention": 0.9, "new_cards_per_day": 20}
    assert c.put("/api/vocab/settings", json={"desired_retention": 0.99, "new_cards_per_day": 5}).status_code == 422
    assert c.put("/api/vocab/settings", json={"desired_retention": 0.85, "new_cards_per_day": 5}).status_code == 200
    dues = [_add(c, f"word{i}")["card"]["due_at"][:10] for i in range(6)]
    days = sorted(set(dues))
    assert len(days) == 2 and dues.count(days[0]) == 5 and dues.count(days[1]) == 1
    forecast = c.get("/api/vocab/forecast").json()
    assert len(forecast["days"]) == 7 and forecast["due"] == 0 and sum(d["count"] for d in forecast["days"]) == 6


# ---------- adding words ----------
def test_add_word_fills_with_ai_dedupes_and_respects_quota(app_client, fake_ai) -> None:  # noqa: ARG001
    c = _user()
    calls = len(fake_ai.calls)
    first = c.post("/api/vocab/cards", json={"word": "Serendipity ", "context": "What a serendipity!"}).json()
    assert first["created"] and first["card"]["meaning_vi"].startswith("nghĩa") and first["card"]["source"] == "manual"
    assert fake_ai.calls[calls:] == ["WordInfo"] and "What a serendipity!" in fake_ai.prompts[-1]
    again = c.post("/api/vocab/cards", json={"word": "serendipity"}).json()
    assert not again["created"] and again["card"]["id"] == first["card"]["id"] and len(fake_ai.calls) == calls + 1

    plan = conftest.TEST_PLAN
    limits = json.loads(conftest._db().execute("SELECT limits FROM plans WHERE code = ?", (plan,)).fetchone()[0])
    set_plan(plan, limits={**limits, "vocabulary": {"daily": 1, "monthly": 0}})
    try:
        assert c.post("/api/vocab/cards", json={"word": "ephemeral"}).status_code == 429
        assert c.post("/api/vocab/cards", json={"word": "ephemeral", "meaning_vi": "phù du"}).status_code == 200
    finally:
        set_plan(plan, limits=limits)


async def test_add_word_service_dedupes(app_client) -> None:  # noqa: ARG001
    async with SessionLocal() as session:
        user_id = (await session.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
        card, created = await srs.add_word(
            session, user_id, {"word": "Tidal  wave", "meaning_vi": "sóng thần"}, "conversation"
        )
        again, created_again = await srs.add_word(session, user_id, {"word": "tidal wave"})
        assert created and not created_again and again.id == card.id and card.source == "conversation"
        await session.rollback()


# ---------- ownership ----------
def test_other_users_cards_and_lessons_are_404(app_client) -> None:  # noqa: ARG001
    owner, other = _user("owner"), _user("other")
    card = _add(owner, "beacon")["card"]
    lesson = _lesson(owner, "vocabulary")
    assert (
        other.post("/api/vocab/answer", json={"question_id": f"vi_to_en:c{card['id']}", "answer": "x"}).status_code
        == 404
    )
    assert other.get(f"/api/vocab/cards/{card['id']}/audio").status_code == 404
    assert other.post(f"/api/lessons/{lesson['id']}/quiz").status_code == 404
    assert other.post(f"/api/lessons/{lesson['id']}/quiz/finish").status_code == 404
    assert other.get(f"/api/lessons/{lesson['id']}/words/0/audio").status_code == 404
    assert other.get(f"/api/vocab/session?mode=lesson&lesson_id={lesson['id']}").status_code == 404
    assert other.post("/api/vocab/answer", json={"question_id": "bogus", "answer": "x"}).status_code == 422
