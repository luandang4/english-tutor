"""Auto-graded review questions built from data we already have — no Gemini call, no quota.

Used by the lesson "Kiểm tra lại" quiz (vocabulary words of the lesson / stored grammar exercises) and by the
review session (cards of the deck, question type by how well the card is known). Questions never carry the
expected answer: grading rebuilds it on the server from the question id.

Question id = "<kind>:<ref>", ref = "c<card id>" (deck card), "w<index>" (word of a lesson) or an exercise id.
"""

import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.constants import ExerciseType
from app.models.lesson import Lesson
from app.models.vocab import VocabCard
from app.schemas.api import QuizQuestion, WordReveal
from app.services import grading, srs

VOCAB_KINDS = ("choose_meaning", "listen_choose", "listen_type", "vi_to_en", "fill_sentence")
GRAMMAR_KINDS = ("grammar_choice", "grammar_fill")
LESSON_QUIZ_KINDS = ("choose_meaning", "listen_type", "vi_to_en", "fill_sentence")
STAGE_KINDS = {  # review session: harder recall as the card matures
    "new": ("choose_meaning", "listen_choose"),
    "learning": ("fill_sentence", "listen_type"),
    "mature": ("vi_to_en",),
}
FALLBACK = ("vi_to_en", "listen_type")
LESSON_QUIZ_SIZE = 10
OPTIONS = 4
BLANK = "___"


class BadQuestion(ValueError):
    """Question id that does not belong to this quiz."""


@dataclass
class WordItem:
    """A word to ask about: a deck card or a word of a lesson."""

    ref: str
    data: Mapping[str, Any]  # word + srs.WORD_FIELDS
    audio_url: str
    card: VocabCard | None = None

    @property
    def word(self) -> str:
        return str(self.data.get("word", ""))

    @property
    def meaning(self) -> str:
        return str(self.data.get("meaning_vi", ""))


@dataclass
class Pools:
    """Distractors for multiple-choice questions."""

    meanings: list[str]
    words: list[str]


def card_item(card: VocabCard) -> WordItem:
    data = {"word": card.word, **{f: getattr(card, f) for f in srs.WORD_FIELDS}}
    return WordItem(ref=f"c{card.id}", data=data, audio_url=f"/api/vocab/cards/{card.id}/audio", card=card)


def lesson_items(lesson: Lesson) -> list[WordItem]:
    words = (lesson.content or {}).get("words", [])
    return [
        WordItem(ref=f"w{i}", data=w, audio_url=f"/api/lessons/{lesson.id}/words/{i}/audio")
        for i, w in enumerate(words)
        if w.get("word")
    ]


def question_id(kind: str, ref: str) -> str:
    return f"{kind}:{ref}"


def parse_question_id(qid: str, kinds: Sequence[str]) -> tuple[str, str]:
    kind, _, ref = qid.partition(":")
    if kind not in kinds or not ref:
        raise BadQuestion("Câu hỏi không hợp lệ.")
    return kind, ref


# ---------- fill the word into its example sentence ----------
def _inflections(token: str) -> set[str]:
    t = token.lower()
    forms = {t, t + "s", t + "es", t + "d", t + "ed", t + "ing", t + "er", t + "est"}
    if t.endswith("e"):
        forms |= {t[:-1] + "ing"}
    if t.endswith("y") and len(t) > 2:
        forms |= {t[:-1] + "ies", t[:-1] + "ied"}
    if len(t) >= 3 and t[-1] not in "aeiouwxy" and t[-2] in "aeiou" and t[-3] not in "aeiou":
        forms |= {t + t[-1] + "ed", t + t[-1] + "ing"}  # stop -> stopped / stopping
    return forms


def word_forms(word: str) -> list[str]:
    """The word and its regular inflections (first or last word inflected for phrases), longest first."""
    tokens = word.lower().split()
    if not tokens:
        return []
    forms = {" ".join(tokens)}
    for f in _inflections(tokens[0]):
        forms.add(" ".join([f, *tokens[1:]]))
    for f in _inflections(tokens[-1]):
        forms.add(" ".join([*tokens[:-1], f]))
    return sorted(forms, key=len, reverse=True)


def blank_sentence(sentence: str, word: str) -> tuple[str, str] | None:
    """(sentence with the word replaced by ___, the form used in the sentence), or None if not found."""
    for form in word_forms(word):
        pattern = r"(?<![\w'])" + r"\s+".join(re.escape(p) for p in form.split()) + r"(?![\w'])"
        m = re.search(pattern, sentence, flags=re.IGNORECASE)
        if m:
            return sentence[: m.start()] + BLANK + sentence[m.end() :], m.group(0)
    return None


# ---------- building questions ----------
def _distractors(correct: str, pool: list[str], rng: random.Random) -> list[str]:
    key = grading.loose(correct)
    seen = {key}
    out = []
    for p in rng.sample(pool, len(pool)):
        k = grading.loose(p)
        if k and k not in seen:
            seen.add(k)
            out.append(p)
        if len(out) == OPTIONS - 1:
            break
    return out


def feasible(kind: str, item: WordItem, pools: Pools) -> bool:
    if kind == "choose_meaning":
        return bool(item.meaning) and len(_distractors(item.meaning, pools.meanings, random.Random(0))) >= 2
    if kind == "listen_choose":
        return len(_distractors(item.word, pools.words, random.Random(0))) >= 2
    if kind == "vi_to_en":
        return bool(item.meaning)
    if kind == "fill_sentence":
        return blank_sentence(str(item.data.get("example_en", "")), item.word) is not None
    return True  # listen_type


def pick_kind(preferred: Sequence[str], item: WordItem, pools: Pools, rng: random.Random) -> str:
    options = [k for k in preferred if feasible(k, item, pools)]
    if options:
        return rng.choice(options)
    return next((k for k in FALLBACK if feasible(k, item, pools)), "listen_type")


def _typed(answer: str) -> dict[str, Any]:
    return {"letters": len(answer), "first_letter": answer[:1]}


def word_question(kind: str, item: WordItem, pools: Pools, rng: random.Random) -> QuizQuestion:
    base: dict[str, Any] = {
        "id": question_id(kind, item.ref),
        "kind": kind,
        "prompt": "",
        "part_of_speech": str(item.data.get("part_of_speech", "")),
        "card_id": item.card.id if item.card else None,
    }
    if kind == "choose_meaning":
        options = [item.meaning, *_distractors(item.meaning, pools.meanings, rng)]
        base |= {"prompt": item.word, "options": rng.sample(options, len(options))}
    elif kind == "listen_choose":
        options = [item.word, *_distractors(item.word, pools.words, rng)]
        base |= {"audio_url": item.audio_url, "options": rng.sample(options, len(options))}
    elif kind == "listen_type":
        base |= {"audio_url": item.audio_url, **_typed(item.word)}
    elif kind == "vi_to_en":
        base |= {"prompt": item.meaning, **_typed(item.word)}
    elif kind == "fill_sentence":
        blanked = blank_sentence(str(item.data.get("example_en", "")), item.word)
        assert blanked is not None
        base |= {"prompt": blanked[0], "hint_vi": str(item.data.get("example_vi", "")), **_typed(blanked[1])}
    return QuizQuestion(**base)


def grammar_question(exercise: dict[str, Any], rng: random.Random) -> QuizQuestion:
    if exercise["type"] == ExerciseType.MULTIPLE_CHOICE:
        options = list(exercise.get("options", []))
        return QuizQuestion(
            id=question_id("grammar_choice", exercise["id"]),
            kind="grammar_choice",
            prompt=exercise["question"],
            hint_vi=exercise.get("instruction_vi", ""),
            options=rng.sample(options, len(options)),
        )
    return QuizQuestion(
        id=question_id("grammar_fill", exercise["id"]),
        kind="grammar_fill",
        prompt=exercise["question"],
        hint_vi=exercise.get("instruction_vi", ""),
    )


def checkable_exercises(lesson: Lesson) -> list[dict[str, Any]]:
    """Stored exercises we can grade by rule (multiple choice / fill in the blank)."""
    kinds = (ExerciseType.MULTIPLE_CHOICE, ExerciseType.FILL_BLANK)
    return [e for e in lesson.exercises if e["type"] in kinds and e.get("answers")]


def lesson_word_questions(items: list[WordItem], pools: Pools, rng: random.Random) -> list[QuizQuestion]:
    """About LESSON_QUIZ_SIZE questions, a different kind for each word; small lessons ask each word twice."""
    if not items:
        return []
    offset = rng.randrange(len(LESSON_QUIZ_KINDS))
    questions: list[QuizQuestion] = []
    used: dict[str, set[str]] = {}
    rounds = 1 if len(items) >= LESSON_QUIZ_SIZE else 2
    for r in range(rounds):
        for i, item in enumerate(items):
            if len(questions) >= LESSON_QUIZ_SIZE:
                break
            want = LESSON_QUIZ_KINDS[(i + offset + r * 2) % len(LESSON_QUIZ_KINDS)]
            preferred = [want] + [k for k in LESSON_QUIZ_KINDS if k != want and k not in used.get(item.ref, set())]
            kind = next((k for k in preferred if feasible(k, item, pools)), None) or pick_kind((), item, pools, rng)
            if kind in used.get(item.ref, set()):
                continue
            used.setdefault(item.ref, set()).add(kind)
            questions.append(word_question(kind, item, pools, rng))
    rng.shuffle(questions)
    return questions


def session_questions(cards: list[VocabCard], pools: Pools, rng: random.Random) -> list[QuizQuestion]:
    out = []
    for card in cards:
        item = card_item(card)
        kind = pick_kind(STAGE_KINDS[srs.card_state(card)], item, pools, rng)
        out.append(word_question(kind, item, pools, rng))
    return out


# ---------- grading ----------
def expected_word_answer(kind: str, item: WordItem) -> str:
    if kind == "choose_meaning":
        return item.meaning
    if kind == "fill_sentence":
        blanked = blank_sentence(str(item.data.get("example_en", "")), item.word)
        return blanked[1] if blanked else item.word
    return item.word


def grade_word(kind: str, item: WordItem, answer: str) -> tuple[str, str]:
    """(result, expected answer) for a vocabulary question."""
    expected = expected_word_answer(kind, item)
    if kind in ("choose_meaning", "listen_choose"):
        return grading.check_choice(answer, expected), expected
    result = grading.check_typed(answer, [expected])
    if result == "wrong" and kind == "fill_sentence" and grading.loose(answer) == grading.loose(item.word):
        result = "near"  # right word, wrong form for this sentence
    return result, expected


def expected_grammar_answer(exercise: dict[str, Any]) -> str:
    return exercise["answers"][0]


def grade_grammar(kind: str, exercise: dict[str, Any], answer: str) -> tuple[str, str]:
    expected = expected_grammar_answer(exercise)
    if kind == "grammar_choice":
        return grading.check_choice(answer, expected), expected
    return grading.check_typed(answer, exercise["answers"]), expected


def reveal(item: WordItem) -> WordReveal:
    fields = {f: str(item.data.get(f) or "") for f in WordReveal.model_fields if f != "word"}
    return WordReveal(word=item.word, **fields)
