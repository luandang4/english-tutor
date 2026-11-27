"""Sentence translation practice: the learner writes Vietnamese sentences in English; AI grades and corrects.

A set is generated once (one Gemini call for all sentences). Grading is rule-first: an answer matching a
reference translation is correct instantly; anything else goes to Gemini. Grading inside a set does not use
quota (the set did), but each sentence allows at most MAX_AI_TRIES graded tries.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import LessonStatus, SentenceSource, Skill
from app.db.session import SessionLocal
from app.models.lesson import Lesson
from app.models.sentence import SentenceAttempt, SentenceSet
from app.models.topic import Topic
from app.models.vocab import VocabCard
from app.schemas.ai import SentenceGrade, SentenceSetDraft
from app.schemas.api import SentenceAttemptOut, SentenceItemOut, SentenceSetDetail, SentenceSetSummary, SentenceStats
from app.services.ai.client import AIUnavailableError, get_ai
from app.services.ai.prompts import (
    GRADER_SYSTEM,
    TEACHER_SYSTEM,
    section_formulas,
    sentence_grading_prompt,
    sentence_set_prompt,
    topic_line,
)
from app.services.grading import normalize
from app.services.tasks import spawn

log = logging.getLogger(__name__)

SET_SIZE = 10
MAX_AI_TRIES = 3  # graded tries per sentence; after that the answer is shown
HINT_PENALTY = 20
DECK_WORDS = 12  # deck practice: the words due soonest
FINAL_VERDICTS = ("correct", "almost", "wrong")


class SentenceError(Exception):
    """A request that cannot be served (shown to the learner as-is)."""


# ---------- what a new set practises ----------
def lesson_focus(lesson: Lesson) -> dict[str, Any]:
    """Words of a vocabulary lesson, or the structures of a grammar lesson."""
    content = lesson.content or {}
    if lesson.skill == Skill.VOCABULARY:
        words = [{"word": w["word"], "meaning_vi": w.get("meaning_vi", "")} for w in content.get("words", [])]
        return {"words": words}
    grammar = [f"{s.get('heading', '')}: {section_formulas(s)}".strip(": ") for s in content.get("sections", [])]
    return {"topic": f"Grammar lesson: {lesson.title}", "grammar": grammar}


async def deck_focus(session: AsyncSession, user_id: int) -> dict[str, Any] | None:
    """The deck words due soonest; None when the deck is empty."""
    cards = (
        await session.scalars(
            select(VocabCard).where(VocabCard.user_id == user_id).order_by(VocabCard.due_at).limit(DECK_WORDS)
        )
    ).all()
    if not cards:
        return None
    return {"words": [{"word": c.word, "meaning_vi": c.meaning_vi} for c in cards]}


def topic_focus(topic: Topic) -> dict[str, Any]:
    return {"topic": topic_line(topic)}


# ---------- creation / generation ----------
async def create_set(
    session: AsyncSession,
    *,
    user_id: int,
    level: str,
    source: SentenceSource,
    focus: dict[str, Any],
    title: str,
    lesson_id: int | None = None,
    topic_id: int | None = None,
) -> SentenceSet:
    row = SentenceSet(
        user_id=user_id,
        source=source,
        lesson_id=lesson_id,
        topic_id=topic_id,
        focus=focus,
        level=level,
        status=LessonStatus.GENERATING,
        title=title[:200],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    spawn(generate_set(row.id), name=f"sentence-set-{row.id}")
    return row


async def retry_generation(session: AsyncSession, row: SentenceSet) -> SentenceSet:
    row.status, row.error = LessonStatus.GENERATING, None
    await session.commit()
    spawn(generate_set(row.id), name=f"sentence-set-{row.id}")
    return row


async def generate_set(set_id: int) -> None:
    """Background job: ask Gemini for all sentences of a set at once."""
    async with SessionLocal() as session:
        row = await session.get(SentenceSet, set_id)
        if row is None:
            return
        try:
            draft, model = await get_ai().generate_json(
                models=get_settings().content_models,
                system=TEACHER_SYSTEM,
                prompt=sentence_set_prompt(level=row.level, focus=row.focus, count=SET_SIZE),
                schema=SentenceSetDraft,
            )
            items = [i.model_dump() for i in draft.items if i.vi.strip() and i.answers][:SET_SIZE]
            if not items:
                raise AIUnavailableError("AI không tạo được câu nào, hãy thử lại.")
            row.items, row.model, row.status, row.error = items, model, LessonStatus.READY, None
            row.title = row.title or draft.title
        except AIUnavailableError as e:
            row.status, row.error = LessonStatus.FAILED, str(e)
        except Exception:
            log.exception("Sentence set %s generation failed", set_id)
            row.status, row.error = LessonStatus.FAILED, "Lỗi không mong muốn khi tạo câu."
        await session.commit()


async def create_retry_set(session: AsyncSession, row: SentenceSet) -> SentenceSet:
    """A new set with the sentences not answered correctly (no AI call, no quota)."""
    states = item_states(row)
    missed = [item for item, st in zip(row.items or [], states, strict=True) if st.verdict != "correct"]
    if not missed:
        raise SentenceError("Không có câu nào sai để luyện lại.")
    retry = SentenceSet(
        user_id=row.user_id,
        source=SentenceSource.RETRY,
        lesson_id=row.lesson_id,
        topic_id=row.topic_id,
        focus=row.focus,
        level=row.level,
        status=LessonStatus.READY,
        title=f"Luyện lại: {row.title}"[:200],
        items=missed,
        model=row.model,
    )
    session.add(retry)
    await session.commit()
    await session.refresh(retry)
    return retry


# ---------- answering ----------
@dataclass
class ItemState:
    tries: int = 0  # graded tries (rule or AI)
    ai_tries: int = 0
    hint_used: bool = False
    revealed: bool = False
    score: int = 0  # best graded score, hint penalty included
    verdict: str | None = None  # best verdict so far; None = not answered
    attempts: list[SentenceAttempt] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return self.verdict == "correct" or self.revealed or self.ai_tries >= MAX_AI_TRIES


def item_states(row: SentenceSet) -> list[ItemState]:
    states = [ItemState() for _ in row.items or []]
    for a in row.attempts:
        if not 0 <= a.item_index < len(states):
            continue
        st = states[a.item_index]
        st.attempts.append(a)
        st.hint_used |= a.hint_used
        if a.verdict == "revealed":
            st.revealed = True
            continue
        st.tries += 1
        st.ai_tries += a.graded_by != "rule"
        if st.verdict is None or a.score > st.score or a.verdict == "correct":
            st.score, st.verdict = a.score, a.verdict
    return states


def _check_index(row: SentenceSet, index: int) -> ItemState:
    if row.status not in (LessonStatus.READY, LessonStatus.COMPLETED) or not row.items:
        raise SentenceError("Bộ câu chưa sẵn sàng.")
    if not 0 <= index < len(row.items):
        raise SentenceError("Câu không tồn tại.")
    st = item_states(row)[index]
    if st.done:
        raise SentenceError("Câu này đã xong, chuyển sang câu tiếp theo.")
    return st


async def _grade(level: str, item: dict, answer: str) -> tuple[SentenceGrade, str]:
    """Reference match = correct without AI; otherwise Gemini judges."""
    if normalize(answer) in {normalize(a) for a in item.get("answers", [])}:
        grade = SentenceGrade(
            verdict="correct",
            score=100,
            corrected=answer.strip(),
            natural=item["answers"][0],
            errors=[],
            target_words_used=True,
            comment_vi="Chính xác!",
        )
        return grade, "rule"
    grade, model = await get_ai().generate_json(
        models=get_settings().grading_models,
        system=GRADER_SYSTEM,
        prompt=sentence_grading_prompt(level=level, item=item, answer=answer),
        schema=SentenceGrade,
        temperature=0.2,
    )
    return grade, model


async def submit_attempt(
    session: AsyncSession, row: SentenceSet, index: int, answer: str, hint_used: bool
) -> SentenceAttempt:
    _check_index(row, index)
    assert row.items is not None
    grade, graded_by = await _grade(row.level, row.items[index], answer)
    score = max(0, min(100, grade.score) - (HINT_PENALTY if hint_used else 0))
    attempt = SentenceAttempt(
        set_id=row.id,
        item_index=index,
        answer=answer.strip(),
        verdict=grade.verdict,
        score=score,
        hint_used=hint_used,
        result=grade.model_dump(),
        graded_by=graded_by,
    )
    return await _save(session, row, attempt)


async def reveal(session: AsyncSession, row: SentenceSet, index: int) -> SentenceAttempt:
    """The learner gives up on a sentence: show the answers."""
    _check_index(row, index)
    attempt = SentenceAttempt(set_id=row.id, item_index=index, answer="", verdict="revealed", score=0)
    return await _save(session, row, attempt)


async def _save(session: AsyncSession, row: SentenceSet, attempt: SentenceAttempt) -> SentenceAttempt:
    session.add(attempt)
    await session.flush()
    await session.refresh(row, ["attempts"])
    if all(st.done for st in item_states(row)):
        row.status = LessonStatus.COMPLETED
    await session.commit()
    await session.refresh(attempt)
    return attempt


# ---------- output ----------
def _stats(row: SentenceSet, states: list[ItemState]) -> SentenceStats:
    verdicts = Counter(st.verdict or "wrong" for st in states if st.done)
    kinds = Counter(
        e.get("kind", "")
        for st in states
        for a in st.attempts
        for e in (a.result or {}).get("errors", [])
        if e.get("kind")
    )
    weak = [
        item.get("grammar_point", "")
        for item, st in zip(row.items or [], states, strict=True)
        if st.done and st.verdict != "correct" and item.get("grammar_point")
    ]
    done = [st for st in states if st.done]
    return SentenceStats(
        done=len(done),
        total=len(states),
        score=round(sum(st.score for st in done) / len(done)) if done else None,
        correct=verdicts["correct"],
        almost=verdicts["almost"],
        wrong=sum(n for v, n in verdicts.items() if v not in ("correct", "almost")),
        error_kinds=dict(kinds.most_common()),
        weak_grammar=list(dict.fromkeys(weak)),
    )


def _item_out(index: int, item: dict, st: ItemState) -> SentenceItemOut:
    return SentenceItemOut(
        index=index,
        vi=item["vi"],
        target_words=item.get("target_words", []),
        grammar_point=item.get("grammar_point", ""),
        hint_vi=item.get("hint_vi", ""),
        hint_words=item.get("hint_words", []),
        answers=item.get("answers", []) if st.done else [],  # hidden until the sentence is finished
        done=st.done,
        verdict=st.verdict,
        score=st.score if st.verdict else None,
        tries_left=max(0, MAX_AI_TRIES - st.ai_tries),
        attempts=[SentenceAttemptOut.model_validate(a) for a in st.attempts],
    )


def set_summary(row: SentenceSet) -> SentenceSetSummary:
    states = item_states(row)
    return SentenceSetSummary(
        id=row.id,
        source=row.source,
        lesson_id=row.lesson_id,
        level=row.level,
        status=row.status,
        title=row.title,
        created_at=row.created_at,
        stats=_stats(row, states),
    )


def set_detail(row: SentenceSet) -> SentenceSetDetail:
    states = item_states(row)
    return SentenceSetDetail(
        **set_summary(row).model_dump(),
        error=row.error,
        items=[_item_out(i, item, st) for i, (item, st) in enumerate(zip(row.items or [], states, strict=True))],
    )
