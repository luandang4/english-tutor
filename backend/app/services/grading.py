"""Exercise grading: deterministic rules first (instant, free), Gemini only when judgement is needed."""

import re
import unicodedata
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.constants import ExerciseType
from app.schemas.ai import AnswerGrade
from app.services.ai.client import get_ai
from app.services.ai.prompts import GRADER_SYSTEM, answer_grading_prompt

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .,!?;:\"'")


@dataclass
class Grade:
    is_correct: bool
    score: int
    feedback_vi: str
    corrected_answer: str
    graded_by: str


async def grade(exercise: dict, answer: str, context: str) -> Grade:
    kind = exercise["type"]
    accepted = [normalize(a) for a in exercise.get("answers", []) if a.strip()]
    given = normalize(answer)

    if kind == ExerciseType.MULTIPLE_CHOICE:
        ok = given in accepted
        return Grade(ok, 100 if ok else 0, "Chính xác!" if ok else "Chưa đúng.", exercise["answers"][0], "rule")

    if kind == ExerciseType.FILL_BLANK and given in accepted:
        return Grade(True, 100, "Chính xác!", answer.strip(), "rule")

    # Open answers (and fill-blank variants not in the key): ask Gemini.
    result, model = await get_ai().generate_json(
        models=get_settings().grading_models,
        system=GRADER_SYSTEM,
        prompt=answer_grading_prompt(exercise=exercise, answer=answer, context=context),
        schema=AnswerGrade,
        temperature=0.2,
    )
    score = max(0, min(100, result.score))
    return Grade(result.is_correct, score, result.feedback_vi, result.corrected_answer, model)


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", text))


# ---------- typed answers in review quizzes (no AI) ----------
NEAR_MIN_LETTERS = 5  # a one-letter slip only counts as "almost" on words this long


def loose(text: str) -> str:
    """Case, whitespace and punctuation-insensitive form ("Boarding-pass!" -> "boarding pass")."""
    t = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    t = re.sub(r"[^\w\s']|_", " ", t).replace("'", "")
    return " ".join(t.split())


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def check_typed(answer: str, accepted: list[str]) -> str:
    """'correct' on an exact (loose) match, 'near' for a one-letter slip on a long word, else 'wrong'."""
    given = loose(answer)
    keys = [k for k in (loose(a) for a in accepted) if k]
    if not given or not keys:
        return "wrong"
    if given in keys:
        return "correct"
    for key in keys:
        if len(key.replace(" ", "")) >= NEAR_MIN_LETTERS and levenshtein(given, key) <= 1:
            return "near"
    return "wrong"


def check_choice(answer: str, correct: str) -> str:
    return "correct" if loose(answer) == loose(correct) else "wrong"
