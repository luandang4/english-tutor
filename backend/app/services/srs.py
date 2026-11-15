"""Vocabulary spaced repetition with FSRS (py-fsrs): adding words, scheduling answers, deck statistics.

Scheduling rules (plan C2 / C6, answer Q8):
- A graded answer on a card that is due is a real review: right -> Good, right with hint / one-letter slip -> Hard,
  wrong -> Again.
- On a card that is NOT due yet, a right answer leaves the schedule alone (early success proves little), a wrong
  answer counts as Again (it was clearly forgotten).
- New words get their first review about a day after they are learned, and at most `new_cards_per_day` new words
  start on the same day; the rest wait for the following days.
"""

from collections import Counter
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fsrs import Card, Rating, Scheduler, State
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import utcnow
from app.models.lesson import Lesson
from app.models.vocab import ReviewLog, SrsSettings, VocabCard
from app.schemas.api import CardOut, DeckStats

MATURE_STABILITY_DAYS = 21
HARD_LAPSES = 4  # forgotten this many times = "từ khó"
DEFAULT_RETENTION = 0.9
DEFAULT_NEW_PER_DAY = 20
WORD_FIELDS = ("ipa", "part_of_speech", "meaning_vi", "definition_en", "example_en", "example_vi")


def word_key(word: str) -> str:
    return " ".join(word.lower().split())


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def local_date(ts: datetime) -> date:
    return ts.astimezone(local_tz()).date()


# ---------- per-learner settings ----------
async def get_srs_settings(session: AsyncSession, user_id: int) -> SrsSettings:
    """The learner's settings; an unsaved default row when they never changed anything."""
    row = await session.get(SrsSettings, user_id)
    return row or SrsSettings(
        user_id=user_id, desired_retention=DEFAULT_RETENTION, new_cards_per_day=DEFAULT_NEW_PER_DAY
    )


async def save_srs_settings(session: AsyncSession, user_id: int, retention: float, new_per_day: int) -> SrsSettings:
    row = await session.get(SrsSettings, user_id)
    if row is None:
        row = SrsSettings(user_id=user_id)
        session.add(row)
    row.desired_retention = retention
    row.new_cards_per_day = new_per_day
    await session.commit()
    return row


def make_scheduler(desired_retention: float = DEFAULT_RETENTION) -> Scheduler:
    # Fuzzing spreads reviews of words learned together over neighbouring days.
    return Scheduler(desired_retention=desired_retention, enable_fuzzing=True)


async def scheduler_for(session: AsyncSession, user_id: int) -> Scheduler:
    return make_scheduler((await get_srs_settings(session, user_id)).desired_retention)


# ---------- when new words start (C6) ----------
def intro_offsets(already: Mapping[int, int], count: int, cap: int) -> list[int]:
    """Day offsets (1 = tomorrow) for `count` new cards, never more than `cap` new cards on one day.

    `already` maps day offset -> new cards already waiting for that day.
    """
    taken = Counter(already)
    out: list[int] = []
    day = 1
    for _ in range(count):
        while taken[day] >= max(1, cap):
            day += 1
        taken[day] += 1
        out.append(day)
    return out


async def _waiting_new_cards(session: AsyncSession, user_id: int, now: datetime) -> Counter[int]:
    """New (never reviewed) cards still waiting for their first day, by day offset from today."""
    rows = await session.scalars(
        select(VocabCard.due_at).where(VocabCard.user_id == user_id, VocabCard.reps == 0, VocabCard.due_at > now)
    )
    today = local_date(now)
    return Counter((local_date(d) - today).days for d in rows.all())


async def first_due_dates(session: AsyncSession, user_id: int, count: int) -> list[datetime]:
    """First review time for `count` new words: ~1 day after learning, respecting the daily new-card cap."""
    now = utcnow()
    cap = (await get_srs_settings(session, user_id)).new_cards_per_day
    offsets = intro_offsets(await _waiting_new_cards(session, user_id, now), count, cap)
    return [now + timedelta(days=d) for d in offsets]


# ---------- adding words ----------
def _new_card(user_id: int, data: Mapping[str, Any], due: datetime, source: str, lesson_id: int | None) -> VocabCard:
    word = " ".join(str(data["word"]).split())
    return VocabCard(
        user_id=user_id,
        lesson_id=lesson_id,
        word_key=word_key(word),
        word=word,
        **{f: str(data.get(f) or "")[:500] for f in WORD_FIELDS},
        fsrs_card=Card(due=due).to_dict(),
        due_at=due,
        source=source,
    )


async def find_card(session: AsyncSession, user_id: int, word: str) -> VocabCard | None:
    return await session.scalar(
        select(VocabCard).where(VocabCard.user_id == user_id, VocabCard.word_key == word_key(word))
    )


async def add_word(
    session: AsyncSession,
    user_id: int,
    data: Mapping[str, Any],
    source: str = "manual",
    lesson_id: int | None = None,
) -> tuple[VocabCard, bool]:
    """Add one word to the learner's deck. `data` has `word` plus any of WORD_FIELDS (missing = empty).

    Returns (card, created). A word already in the deck (same word_key) returns the existing card untouched.
    Flushes but does not commit. `source`: lesson / manual / conversation / writing.
    """
    existing = await find_card(session, user_id, str(data["word"]))
    if existing is not None:
        return existing, False
    (due,) = await first_due_dates(session, user_id, 1)
    card = _new_card(user_id, data, due, source, lesson_id)
    session.add(card)
    await session.flush()
    return card, True


async def add_lesson_words(session: AsyncSession, lesson: Lesson) -> int:
    """Add the lesson's words to the deck (skips words already there). Returns number added."""
    assert lesson.user_id is not None
    words = (lesson.content or {}).get("words", [])
    keys = {word_key(w["word"]): w for w in words if w.get("word")}
    if not keys:
        return 0
    existing = set(
        (
            await session.scalars(
                select(VocabCard.word_key).where(VocabCard.user_id == lesson.user_id, VocabCard.word_key.in_(keys))
            )
        ).all()
    )
    fresh = [w for key, w in keys.items() if key not in existing]
    dues = await first_due_dates(session, lesson.user_id, len(fresh))
    for w, due in zip(fresh, dues, strict=True):
        session.add(_new_card(lesson.user_id, w, due, "lesson", lesson.id))
    return len(fresh)


async def lesson_words_in_deck(session: AsyncSession, lesson: Lesson) -> int:
    keys = [word_key(w["word"]) for w in (lesson.content or {}).get("words", []) if w.get("word")]
    if not keys:
        return 0
    q = select(func.count()).where(VocabCard.user_id == lesson.user_id, VocabCard.word_key.in_(keys))
    return await session.scalar(q) or 0


# ---------- card views ----------
def card_state(row: VocabCard) -> str:
    if row.reps == 0:
        return "new"
    fs = row.fsrs_card
    if fs.get("state") == State.Review.value and (fs.get("stability") or 0) >= MATURE_STABILITY_DAYS:
        return "mature"
    return "learning"


def is_hard(row: VocabCard) -> bool:
    return row.lapses >= HARD_LAPSES


def _fmt(delta: timedelta) -> str:
    s = delta.total_seconds()
    if s < 60:
        return "<1 phút"
    if s < 3600:
        return f"{round(s / 60)} phút"
    if s < 86400:
        return f"{round(s / 3600)} giờ"
    if s < 86400 * 30:
        return f"{round(s / 86400)} ngày"
    if s < 86400 * 365:
        return f"{round(s / 86400 / 30)} tháng"
    return f"{s / 86400 / 365:.1f} năm"


def card_out(
    row: VocabCard,
    now: datetime | None = None,
    scheduler: Scheduler | None = None,
    lesson: Lesson | None = None,
) -> CardOut:
    """Card DTO + the interval each rating button would schedule (+ lesson title / tips when given)."""
    now = now or utcnow()
    scheduler = scheduler or make_scheduler()
    intervals = {}
    for rating in Rating:
        nxt, _ = scheduler.review_card(Card.from_dict(row.fsrs_card), rating, review_datetime=now)
        intervals[str(int(rating))] = _fmt(nxt.due - now)
    out = CardOut.model_validate(row)
    out.intervals = intervals
    out.state = card_state(row)  # type: ignore[assignment]
    out.is_hard = is_hard(row)
    if lesson is not None:
        out.lesson_title = lesson.title
        if out.is_hard:
            out.tips_vi = list((lesson.content or {}).get("tips_vi", []))
    return out


async def lessons_by_id(session: AsyncSession, ids: set[int]) -> dict[int, Lesson]:
    if not ids:
        return {}
    return {x.id: x for x in (await session.scalars(select(Lesson).where(Lesson.id.in_(ids)))).all()}


# ---------- answers -> schedule ----------
def rating_for(result: str, hinted: bool = False) -> Rating:
    """Quiz outcome -> FSRS rating: wrong = Again, one-letter slip or hint = Hard, right = Good."""
    if result == "wrong":
        return Rating.Again
    if result == "near" or hinted:
        return Rating.Hard
    return Rating.Good


def _apply_review(row: VocabCard, rating: Rating, scheduler: Scheduler, now: datetime) -> None:
    was_review = row.fsrs_card.get("state") == State.Review.value
    card, _ = scheduler.review_card(Card.from_dict(row.fsrs_card), rating, review_datetime=now)
    row.fsrs_card = card.to_dict()
    row.due_at = card.due
    row.reps += 1
    if rating == Rating.Again and was_review:  # forgot a learned card
        row.lapses += 1
    row.last_reviewed_at = now


async def record_answer(
    session: AsyncSession,
    row: VocabCard,
    rating: Rating | int,
    *,
    scheduler: Scheduler,
    source: str,
    counts: bool = True,
    now: datetime | None = None,
) -> bool:
    """The single entry point for every graded answer (quiz, review session, flip card). Logs it and applies the
    schedule rule: due -> review; not due -> only Again moves it. `counts=False` (re-queued retry) never moves it.
    Returns True when the schedule changed."""
    now = now or utcnow()
    rating = Rating(rating)
    changes = counts and (row.due_at <= now or rating == Rating.Again)
    if changes:
        _apply_review(row, rating, scheduler, now)
    session.add(ReviewLog(card_id=row.id, rating=int(rating), reviewed_at=now, counted=changes, source=source))
    return changes


async def review(session: AsyncSession, row: VocabCard, rating: int, scheduler: Scheduler | None = None) -> bool:
    """Self-rated flip card ("Ôn nhanh")."""
    scheduler = scheduler or await scheduler_for(session, row.user_id or 0)
    return await record_answer(session, row, rating, scheduler=scheduler, source="flip")


# ---------- statistics ----------
async def due_count(session: AsyncSession, user_id: int) -> int:
    q = select(func.count()).where(VocabCard.user_id == user_id, VocabCard.due_at <= utcnow())
    return await session.scalar(q) or 0


async def deck_stats(session: AsyncSession, day_start: datetime, user_id: int) -> DeckStats:
    now = utcnow()
    rows = (await session.scalars(select(VocabCard).where(VocabCard.user_id == user_id))).all()
    states = Counter(card_state(r) for r in rows)
    reviewed_today = await session.scalar(
        select(func.count())
        .select_from(ReviewLog)
        .join(VocabCard)
        .where(VocabCard.user_id == user_id, ReviewLog.reviewed_at >= day_start)
    )
    return DeckStats(
        total=len(rows),
        due=sum(1 for r in rows if r.due_at <= now),
        new=states["new"],
        learning=states["learning"],
        mature=states["mature"],
        reviewed_today=reviewed_today or 0,
        hard=sum(1 for r in rows if is_hard(r)),
    )


def retrievability(row: VocabCard, scheduler: Scheduler, now: datetime) -> float | None:
    """FSRS probability (0-1) of recalling the card now; None for cards never reviewed."""
    if row.reps == 0 or not row.fsrs_card.get("stability"):
        return None
    return scheduler.get_card_retrievability(Card.from_dict(row.fsrs_card), current_datetime=now)
