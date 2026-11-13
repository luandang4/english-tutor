"""Domain constants shared by AI prompts, API validation and the UI."""

from enum import StrEnum


class Skill(StrEnum):
    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"
    WRITING = "writing"


class LessonStatus(StrEnum):
    GENERATING = "generating"
    READY = "ready"
    COMPLETED = "completed"
    FAILED = "failed"


class SubmissionStatus(StrEnum):
    GRADING = "grading"
    GRADED = "graded"
    FAILED = "failed"


class ExerciseType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_blank"
    REWRITE = "rewrite"
    PRODUCE = "produce"


# CEFR level -> guidance for the AI (English) and a label for the UI (Vietnamese).
LEVELS: dict[str, dict[str, str]] = {
    "A1": {
        "label": "A1 – Mới bắt đầu",
        "ai": "absolute beginner: very short sentences, the 500 most common words",
    },
    "A2": {
        "label": "A2 – Sơ cấp",
        "ai": "elementary: short simple sentences, everyday vocabulary, present/past simple",
    },
    "B1": {
        "label": "B1 – Trung cấp",
        "ai": "intermediate: everyday topics, common phrasal verbs and idioms, clear structures",
    },
    "B2": {
        "label": "B2 – Trung cao cấp",
        "ai": "upper-intermediate: natural language, wider vocabulary, complex sentences",
    },
    "C1": {
        "label": "C1 – Nâng cao",
        "ai": "advanced: nuanced, idiomatic and precise language, sophisticated structures",
    },
}
DEFAULT_LEVEL = "B1"

LEARNER_PROFILE = "a Vietnamese adult learning English"
