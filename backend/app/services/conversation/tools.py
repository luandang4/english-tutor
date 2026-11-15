"""Emma's on-screen function calls (Gemini Live): declarations and parsing of the model's arguments.

Each tool only puts text on the learner's screen. Arguments come from the model, so they are cleaned and
length-capped here; anything malformed is ignored (the call is answered "unknown" and nothing is shown).
"""

from dataclasses import asdict, dataclass
from typing import Any

from google.genai import types

from app.services.conversation.tutor import FEEDBACK_TOOL, HINT_TOOL, TRANSLATE_TOOL, VIETNAMESE_HINT_LEVELS

FEEDBACK_KINDS = ("correction", "upgrade")
MAX_TEXT = 2000
MAX_SHORT = 500
MAX_FRAMES = 3
MAX_KEYWORDS = 5

TRANSLATE_DECLARATION = types.FunctionDeclaration(
    name=TRANSLATE_TOOL,
    description=(
        "Show a Vietnamese translation on the learner's screen (text only, not spoken). Call it when the learner "
        "says they did not understand what you said, or asks what something you said means."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "english": {"type": "string", "description": "The English you said that the learner did not understand."},
            "vietnamese": {"type": "string", "description": "Natural Vietnamese translation of that English."},
        },
        "required": ["english", "vietnamese"],
    },
)

FEEDBACK_DECLARATION = types.FunctionDeclaration(
    name=FEEDBACK_TOOL,
    description=(
        "Show a feedback card under the learner's sentence (text only, not spoken). Call it every time you "
        "correct a real error (kind 'correction') or offer a better way to say a correct sentence (kind 'upgrade')."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": list(FEEDBACK_KINDS)},
            "original": {"type": "string", "description": "The learner's words, as they said them."},
            "better": {"type": "string", "description": "The corrected or upgraded sentence."},
            "explain_vi": {
                "type": "string",
                "description": "Very short reason in Vietnamese, e.g. 'quá khứ: go → went'.",
            },
        },
        "required": ["kind", "original", "better", "explain_vi"],
    },
)

HINT_DECLARATION = types.FunctionDeclaration(
    name=HINT_TOOL,
    description=(
        "Show a 'how to answer' card on the learner's screen (text only, not spoken) when they are stuck: your "
        "question, 2-3 sentence frames they can complete, and 3-5 useful keywords."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "question_en": {"type": "string", "description": "The question you asked, in English."},
            "question_vi": {"type": "string", "description": "Its Vietnamese meaning (levels A1-B1 only, else empty)."},
            "frames": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-3 sentence starters at the learner's level, e.g. 'In my free time, I usually …'.",
            },
            "keywords": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "en": {"type": "string"},
                        "vi": {"type": "string", "description": "Vietnamese meaning (A1-B1 only, else empty)."},
                    },
                    "required": ["en"],
                },
                "description": "3-5 useful words or phrases for the answer.",
            },
        },
        "required": ["question_en", "frames", "keywords"],
    },
)

DECLARATIONS = [TRANSLATE_DECLARATION, FEEDBACK_DECLARATION, HINT_DECLARATION]


def _text(value: Any, limit: int = MAX_SHORT) -> str:
    return " ".join(str(value or "").split())[:limit]


@dataclass(frozen=True)
class Translation:
    english: str
    vietnamese: str

    def to_message(self) -> dict[str, Any]:
        return {"type": "translation", "english": self.english, "vietnamese": self.vietnamese}


@dataclass(frozen=True)
class Feedback:
    kind: str  # correction | upgrade
    original: str
    better: str
    explain_vi: str

    def to_message(self) -> dict[str, Any]:
        return {"type": "feedback", **asdict(self)}


@dataclass(frozen=True)
class Keyword:
    en: str
    vi: str


@dataclass(frozen=True)
class Hint:
    question_en: str
    question_vi: str
    frames: tuple[str, ...]
    keywords: tuple[Keyword, ...]

    def to_message(self) -> dict[str, Any]:
        return {"type": "hint", **self.fields()}

    def fields(self) -> dict[str, Any]:
        return {
            "question_en": self.question_en,
            "question_vi": self.question_vi,
            "frames": list(self.frames),
            "keywords": [asdict(k) for k in self.keywords],
        }


def parse_translation(call: types.FunctionCall) -> Translation | None:
    """The tutor's `show_vietnamese` call as clean text, or None for any other / empty call."""
    if call.name != TRANSLATE_TOOL:
        return None
    args = call.args or {}
    vietnamese = str(args.get("vietnamese") or "").strip()[:MAX_TEXT]
    if not vietnamese:
        return None
    return Translation(str(args.get("english") or "").strip()[:MAX_TEXT], vietnamese)


def parse_feedback(call: types.FunctionCall) -> Feedback | None:
    """The tutor's `show_feedback` call, or None if it is another tool or lacks a kind / better sentence."""
    if call.name != FEEDBACK_TOOL:
        return None
    args = call.args or {}
    kind = _text(args.get("kind")).lower()
    better = _text(args.get("better"))
    if kind not in FEEDBACK_KINDS or not better:
        return None
    return Feedback(kind, _text(args.get("original")), better, _text(args.get("explain_vi")))


def _keywords(raw: Any, vietnamese: bool) -> tuple[Keyword, ...]:
    items = raw if isinstance(raw, list) else []
    out = []
    for item in items:
        if isinstance(item, dict) and (en := _text(item.get("en"), 120)):
            out.append(Keyword(en, _text(item.get("vi"), 120) if vietnamese else ""))
    return tuple(out[:MAX_KEYWORDS])


def parse_hint(call: types.FunctionCall, level: str) -> Hint | None:
    """The tutor's `show_hint` call. Vietnamese is dropped above B1 (hints are English-only there)."""
    if call.name != HINT_TOOL:
        return None
    args = call.args or {}
    vietnamese = level in VIETNAMESE_HINT_LEVELS
    raw_frames = args.get("frames") if isinstance(args.get("frames"), list) else []
    frames = tuple(f for f in (_text(x, 200) for x in raw_frames) if f)[:MAX_FRAMES]
    keywords = _keywords(args.get("keywords"), vietnamese)
    if not frames and not keywords:
        return None
    question_vi = _text(args.get("question_vi")) if vietnamese else ""
    return Hint(_text(args.get("question_en")), question_vi, frames, keywords)


ToolCard = Translation | Feedback | Hint


def parse_tool_call(call: types.FunctionCall, level: str) -> ToolCard | None:
    """Any of Emma's on-screen tools, parsed and cleaned; None for unknown or malformed calls."""
    return parse_translation(call) or parse_feedback(call) or parse_hint(call, level)
