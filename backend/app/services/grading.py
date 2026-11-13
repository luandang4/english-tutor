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
