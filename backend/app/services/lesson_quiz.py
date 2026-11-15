"""Lesson "Kiểm tra lại" (plan C1 / C8): a quiz rebuilt from the lesson's own data, any time, without Gemini.

Vocabulary: ~10 questions over the lesson's words (choose the meaning, listen and type, Vietnamese -> English,
fill the word into its example). Answers on words already in the deck update their FSRS schedule by the usual
rule (srs.record_answer). Grammar: the stored multiple-choice / fill-in exercises, previously missed ones first;
finishing a full re-check on its due date advances the 1-3-7-14 day schedule.
"""

import random
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Skill
from app.db.base import utcnow
from app.models.lesson import Lesson, LessonRecheck
from app.schemas.api import AnswerIn, AnswerOut, QuizItemResult, QuizOut, QuizQuestion, QuizResultOut
from app.services import quiz, recheck, srs
from app.services.review_session import load_pools


class QuizError(ValueError):
    pass


# ---------- start ----------
def _missed_exercises(lesson: Lesson, row: LessonRecheck) -> set[str]:
    missed = {a.exercise_id for a in lesson.attempts if not a.is_correct}
    return missed | set(row.wrong_items or [])


async def _vocab_questions(
    session: AsyncSession, lesson: Lesson, row: LessonRecheck, only_wrong: bool, rng: random.Random
) -> list[QuizQuestion]:
    items = quiz.lesson_items(lesson)
    if only_wrong and row.wrong_items:
        wrong = set(row.wrong_items)
        items = [i for i in items if srs.word_key(i.word) in wrong] or items
    pools = await load_pools(session, lesson.user_id or 0, quiz.lesson_items(lesson))
    return quiz.lesson_word_questions(items, pools, rng)


def _grammar_questions(lesson: Lesson, row: LessonRecheck, only_wrong: bool, rng: random.Random) -> list[QuizQuestion]:
    exercises = quiz.checkable_exercises(lesson)
    missed = _missed_exercises(lesson, row)
    if only_wrong and row.wrong_items:
        exercises = [e for e in exercises if e["id"] in set(row.wrong_items)] or exercises
    ordered = [e for e in exercises if e["id"] in missed] + [e for e in exercises if e["id"] not in missed]
    return [quiz.grammar_question(e, rng) for e in ordered[: quiz.LESSON_QUIZ_SIZE]]


async def start_quiz(session: AsyncSession, lesson: Lesson, only_wrong: bool = False) -> QuizOut:
    if not lesson.content:
        raise QuizError("Bài học chưa sẵn sàng.")
    rng = random.Random()
    row = await recheck.get_recheck(session, lesson)
    if lesson.skill == Skill.VOCABULARY:
        questions = await _vocab_questions(session, lesson, row, only_wrong, rng)
    else:
        questions = _grammar_questions(lesson, row, only_wrong, rng)
    if not questions:
        raise QuizError("Bài này chưa có nội dung để kiểm tra lại.")
    recheck.start_run(row, [q.id for q in questions], full=not only_wrong)
    await session.commit()
    return QuizOut(lesson_id=lesson.id, skill=lesson.skill, title=lesson.title, questions=questions)


# ---------- answer ----------
def _word_item(lesson: Lesson, ref: str) -> quiz.WordItem:
    item = next((i for i in quiz.lesson_items(lesson) if i.ref == ref), None)
    if item is None:
        raise quiz.BadQuestion("Câu hỏi không hợp lệ.")
    return item


def _exercise(lesson: Lesson, exercise_id: str) -> dict[str, Any]:
    ex = next((e for e in quiz.checkable_exercises(lesson) if e["id"] == exercise_id), None)
    if ex is None:
        raise quiz.BadQuestion("Câu hỏi không hợp lệ.")
    return ex


async def _answer_word(session: AsyncSession, lesson: Lesson, body: AnswerIn) -> AnswerOut:
    kind, ref = quiz.parse_question_id(body.question_id, quiz.VOCAB_KINDS)
    item = _word_item(lesson, ref)
    result, expected = quiz.grade_word(kind, item, body.answer)
    out = AnswerOut(result=result, expected=expected, word=quiz.reveal(item))  # type: ignore[arg-type]
    card = await srs.find_card(session, lesson.user_id or 0, item.word)
    if card is not None:
        rating = srs.rating_for(result, body.hinted)
        scheduler = await srs.scheduler_for(session, card.user_id or 0)
        changed = await srs.record_answer(session, card, rating, scheduler=scheduler, source="quiz")
        out.card_id, out.next_review_at = card.id, card.due_at
        out.rating = int(rating) if changed else None
    return out


def _answer_grammar(lesson: Lesson, body: AnswerIn) -> AnswerOut:
    kind, ref = quiz.parse_question_id(body.question_id, quiz.GRAMMAR_KINDS)
    ex = _exercise(lesson, ref)
    result, expected = quiz.grade_grammar(kind, ex, body.answer)
    return AnswerOut(result=result, expected=expected, explanation_vi=ex.get("explanation_vi", ""))  # type: ignore[arg-type]


async def answer_quiz(session: AsyncSession, lesson: Lesson, body: AnswerIn) -> AnswerOut:
    if lesson.skill == Skill.VOCABULARY:
        out = await _answer_word(session, lesson, body)
    else:
        out = _answer_grammar(lesson, body)
    row = await recheck.get_recheck(session, lesson)
    recheck.record_result(row, body.question_id, out.result)
    await session.commit()
    return out


# ---------- finish ----------
def _item_result(lesson: Lesson, qid: str, result: str | None) -> tuple[QuizItemResult, str]:
    """(result row, key remembered when wrong: word key or exercise id)."""
    if lesson.skill == Skill.VOCABULARY:
        kind, ref = quiz.parse_question_id(qid, quiz.VOCAB_KINDS)
        item = _word_item(lesson, ref)
        expected = quiz.expected_word_answer(kind, item)
        return QuizItemResult(question_id=qid, label=item.word, expected=expected, result=result), srs.word_key(
            item.word
        )
    _, ref = quiz.parse_question_id(qid, quiz.GRAMMAR_KINDS)
    ex = _exercise(lesson, ref)
    label = ex["question"]
    return QuizItemResult(question_id=qid, label=label, expected=quiz.expected_grammar_answer(ex), result=result), ex[
        "id"
    ]


def _score(items: list[QuizItemResult]) -> float:
    right = sum(1 for i in items if i.result in ("correct", "near"))
    return round(100 * right / len(items), 1) if items else 0.0


async def finish_quiz(session: AsyncSession, lesson: Lesson) -> QuizResultOut:
    row = await recheck.get_recheck(session, lesson)
    current = row.current or {}
    if not current.get("items"):
        raise QuizError("Không có bài kiểm tra nào đang làm.")
    answers: dict[str, str] = current.get("answers", {})
    items: list[QuizItemResult] = []
    wrong: list[str] = []
    for qid in current["items"]:
        try:
            item, key = _item_result(lesson, qid, answers.get(qid))
        except quiz.BadQuestion:
            continue  # lesson content changed since the quiz started
        items.append(item)
        if item.result in (None, "wrong") and key not in wrong:
            wrong.append(key)
    score = _score(items)
    now = utcnow()
    row.wrong_items = wrong
    row.runs += 1
    row.last_done_at = now
    if current.get("full"):
        row.last_score = score
        recheck.advance_schedule(lesson, row, score, now)
    row.current = {}
    await session.commit()
    return QuizResultOut(
        score=score,
        total=len(items),
        correct=sum(1 for i in items if i.result == "correct"),
        near=sum(1 for i in items if i.result == "near"),
        wrong=sum(1 for i in items if i.result in (None, "wrong")),
        items=items,
        next_recheck_at=recheck.recheck_due_at(lesson, row),
        recheck_step=row.step,
    )
