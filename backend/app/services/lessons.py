"""Vocabulary & grammar lessons: AI generation, exercise attempts, completion."""

import logging
import random
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import ExerciseType, LessonStatus, Skill
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.lesson import ExerciseAttempt, Lesson
from app.models.topic import Topic
from app.models.vocab import VocabCard
from app.schemas.ai import ExerciseDraft, ExerciseSetDraft, GrammarLessonDraft, VocabLessonDraft
from app.schemas.api import AttemptOut, ExerciseOut, ExerciseResult, LessonDetail, LessonSummary, TopicOut
from app.services import grading, srs
from app.services.ai.client import AIUnavailableError, get_ai
from app.services.ai.prompts import (
    TEACHER_SYSTEM,
    grammar_lesson_prompt,
    new_exercises_prompt,
    vocab_lesson_prompt,
)
from app.services.speech import tts
from app.services.tasks import spawn

log = logging.getLogger(__name__)


# ---------- creation / generation ----------
async def create_lesson(session: AsyncSession, topic: Topic, level: str, user_id: int) -> Lesson:
    lesson = Lesson(
        user_id=user_id,
        topic_id=topic.id,
        skill=topic.skill,
        level=level,
        status=LessonStatus.GENERATING,
        title=topic.title,
    )
    session.add(lesson)
    await session.commit()
    await session.refresh(lesson)
    spawn(generate_lesson(lesson.id), name=f"lesson-{lesson.id}")
    return lesson


async def generate_lesson(lesson_id: int) -> None:
    """Background job: ask Gemini for the lesson body and store it."""
    async with SessionLocal() as session:
        lesson = await session.get(Lesson, lesson_id)
        if lesson is None:
            return
        try:
            if lesson.skill == Skill.VOCABULARY:
                known = (await session.scalars(select(VocabCard.word).where(VocabCard.user_id == lesson.user_id))).all()
                draft, model = await get_ai().generate_json(
                    models=get_settings().content_models,
                    system=TEACHER_SYSTEM,
                    prompt=vocab_lesson_prompt(lesson.topic, lesson.level, list(known)),
                    schema=VocabLessonDraft,
                )
            else:
                draft, model = await get_ai().generate_json(
                    models=get_settings().content_models,
                    system=TEACHER_SYSTEM,
                    prompt=grammar_lesson_prompt(lesson.topic, lesson.level),
                    schema=GrammarLessonDraft,
                )
            content = draft.model_dump()
            content["exercises"] = normalize_exercises(draft.exercises)
            lesson.content = content
            lesson.title = draft.title or lesson.topic.title
            lesson.model = model
            lesson.status = LessonStatus.READY
            lesson.error = None
        except AIUnavailableError as e:
            lesson.status, lesson.error = LessonStatus.FAILED, str(e)
        except Exception:
            log.exception("Lesson %s generation failed", lesson_id)
            lesson.status, lesson.error = LessonStatus.FAILED, "Lỗi không mong muốn khi tạo bài học."
        await session.commit()
        if lesson.status == LessonStatus.READY and lesson.skill == Skill.VOCABULARY and get_settings().tts_prefetch:
            words = [w["word"] for w in (lesson.content or {}).get("words", [])]
            spawn(tts.prefetch(words), name=f"lesson-{lesson_id}-audio")


async def retry_lesson(session: AsyncSession, lesson: Lesson) -> Lesson:
    lesson.status, lesson.error = LessonStatus.GENERATING, None
    await session.commit()
    spawn(generate_lesson(lesson.id), name=f"lesson-{lesson.id}")
    return lesson


def normalize_exercises(drafts: list[ExerciseDraft], round_: int = 1) -> list[dict[str, Any]]:
    """Assign stable ids (unique per round), make sure MC answers are among the options, shuffle options."""
    prefix = "" if round_ == 1 else f"r{round_}"
    out = []
    for i, d in enumerate(drafts, start=1):
        ex = d.model_dump()
        ex["id"] = f"{prefix}e{i}"
        ex["answers"] = [a for a in ex["answers"] if a.strip()]
        if d.type == ExerciseType.MULTIPLE_CHOICE:
            if not ex["answers"]:
                continue
            options = list(dict.fromkeys(o for o in ex["options"] if o.strip()))
            norm = {grading.normalize(o): o for o in options}
            correct = norm.get(grading.normalize(ex["answers"][0]))
            if correct is None:
                options.append(ex["answers"][0])
                correct = ex["answers"][0]
            ex["answers"] = [correct]
            random.shuffle(options)
            ex["options"] = options
        else:
            ex["options"] = []
        out.append(ex)
    return out


# ---------- new exercise rounds ----------
async def regenerate_exercises(session: AsyncSession, lesson: Lesson) -> Lesson:
    lesson.exercises_status, lesson.exercises_error = "generating", None
    await session.commit()
    spawn(generate_exercise_round(lesson.id), name=f"lesson-{lesson.id}-exercises")
    return lesson


async def generate_exercise_round(lesson_id: int) -> None:
    """Background job: a fresh exercise set for an existing lesson, avoiding every earlier question."""
    async with SessionLocal() as session:
        lesson = await session.get(Lesson, lesson_id)
        if lesson is None or not lesson.content:
            return
        content = dict(lesson.content)
        past = [*content.get("past_questions", []), *(e["question"] for e in lesson.exercises)]
        try:
            draft, _ = await get_ai().generate_json(
                models=get_settings().content_models,
                system=TEACHER_SYSTEM,
                prompt=new_exercises_prompt(
                    skill=lesson.skill, level=lesson.level, title=lesson.title, content=content, past_questions=past
                ),
                schema=ExerciseSetDraft,
                temperature=0.9,
            )
            round_ = lesson.exercise_round + 1
            exercises = normalize_exercises(draft.exercises, round_)
            if not exercises:
                raise AIUnavailableError("Gemini không trả về bài tập hợp lệ, hãy thử lại.")
            content["past_questions"] = past
            content["exercises"] = exercises
            lesson.content = content  # reassign so SQLAlchemy persists the JSON change
            lesson.exercise_round = round_
            lesson.exercises_status, lesson.exercises_error = None, None
            if lesson.status == LessonStatus.COMPLETED:
                lesson.status = LessonStatus.READY  # new round in progress; completes again when all answered
        except AIUnavailableError as e:
            lesson.exercises_status, lesson.exercises_error = "failed", str(e)
        except Exception:
            log.exception("Lesson %s exercise regeneration failed", lesson_id)
            lesson.exercises_status, lesson.exercises_error = "failed", "Lỗi không mong muốn khi tạo bài tập."
        await session.commit()


# ---------- views ----------
def _result_for(ex: dict[str, Any], attempts: list[ExerciseAttempt]) -> ExerciseResult | None:
    mine = [a for a in attempts if a.exercise_id == ex["id"]]
    if not mine:
        return None
    last = mine[-1]
    return ExerciseResult(
        answer=last.answer,
        is_correct=last.is_correct,
        score=last.score,
        feedback_vi=last.feedback_vi,
        corrected_answer=last.corrected_answer,
        answers=ex.get("answers", []),
        explanation_vi=ex.get("explanation_vi", ""),
        attempts=len(mine),
    )


def exercise_out(ex: dict[str, Any], attempts: list[ExerciseAttempt]) -> ExerciseOut:
    return ExerciseOut(
        id=ex["id"],
        type=ex["type"],
        instruction_vi=ex.get("instruction_vi", ""),
        question=ex["question"],
        options=ex.get("options", []),
        result=_result_for(ex, attempts),
    )


def lesson_summary(lesson: Lesson) -> LessonSummary:
    current = {e["id"] for e in lesson.exercises}
    answered = {a.exercise_id for a in lesson.attempts} & current
    return LessonSummary(
        id=lesson.id,
        skill=lesson.skill,
        level=lesson.level,
        status=lesson.status,
        title=lesson.title,
        score=lesson.score,
        created_at=lesson.created_at,
        completed_at=lesson.completed_at,
        topic=TopicOut.model_validate(lesson.topic),
        exercise_count=len(lesson.exercises),
        answered_count=len(answered),
    )


async def lesson_detail(session: AsyncSession, lesson: Lesson) -> LessonDetail:
    body = {k: v for k, v in (lesson.content or {}).items() if k != "exercises"} if lesson.content else None
    in_deck = await srs.lesson_words_in_deck(session, lesson) if lesson.skill == Skill.VOCABULARY else 0
    return LessonDetail(
        **lesson_summary(lesson).model_dump(),
        error=lesson.error,
        content=body,
        exercises=[exercise_out(ex, lesson.attempts) for ex in lesson.exercises],
        in_deck=in_deck,
        exercise_round=lesson.exercise_round,
        exercises_status=lesson.exercises_status,
        exercises_error=lesson.exercises_error,
    )


# ---------- attempts ----------
def _lesson_context(lesson: Lesson) -> str:
    c = lesson.content or {}
    if lesson.skill == Skill.VOCABULARY:
        words = ", ".join(w["word"] for w in c.get("words", []))
        return f"Vocabulary lesson '{lesson.title}' (CEFR {lesson.level}); target words: {words}"
    return f"Grammar lesson '{lesson.title}' (CEFR {lesson.level})"


async def submit_attempt(session: AsyncSession, lesson: Lesson, exercise: dict[str, Any], answer: str) -> AttemptOut:
    g = await grading.grade(exercise, answer, _lesson_context(lesson))
    attempt = ExerciseAttempt(
        lesson_id=lesson.id,
        exercise_id=exercise["id"],
        answer=answer.strip(),
        is_correct=g.is_correct,
        score=g.score,
        feedback_vi=g.feedback_vi,
        corrected_answer=g.corrected_answer,
        graded_by=g.graded_by,
    )
    lesson.attempts.append(attempt)

    cards_added = 0
    best: dict[str, int] = {}
    for a in lesson.attempts:
        best[a.exercise_id] = max(best.get(a.exercise_id, 0), a.score)
    ids = [ex["id"] for ex in lesson.exercises]
    if all(i in best for i in ids):
        lesson.score = round(sum(best[i] for i in ids) / len(ids), 1)
        if lesson.status == LessonStatus.READY:
            lesson.status = LessonStatus.COMPLETED
            lesson.completed_at = utcnow()  # latest round completion
            if lesson.skill == Skill.VOCABULARY:
                cards_added = await srs.add_lesson_words(session, lesson)
    await session.commit()
    return AttemptOut(
        exercise=exercise_out(exercise, lesson.attempts),
        lesson_status=lesson.status,
        lesson_score=lesson.score,
        cards_added=cards_added,
    )


async def fail_stale_jobs(session: AsyncSession) -> None:
    """Jobs interrupted by a restart can never finish: mark them failed so the UI offers a retry."""
    from app.models.writing import WritingSubmission, WritingTask

    msg = "Máy chủ khởi động lại khi đang xử lý, vui lòng thử lại."
    for model, status in (
        (Lesson, LessonStatus.GENERATING),
        (WritingTask, LessonStatus.GENERATING),
        (WritingSubmission, "grading"),
    ):
        for row in (await session.scalars(select(model).where(model.status == status))).all():
            row.status, row.error = "failed", msg
    for row in (await session.scalars(select(Lesson).where(Lesson.exercises_status == "generating"))).all():
        row.exercises_status, row.exercises_error = "failed", msg
    await session.commit()
