"""Pronunciation evidence for voice conversations (Azure Pronunciation Assessment, the only Azure usage).

The tutor model must not judge pronunciation from a transcript, so each spoken learner turn is assessed on
the real audio: `LearnerTurn` collects the mic audio + transcript of one turn, `assess_turn` scores it, and
`tutor_note` turns the result into a short message for the tutor model.
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import numpy as np

from app.services.speech import assessment, azure

log = logging.getLogger(__name__)

RATE = azure.SAMPLE_RATE
BYTES_PER_SECOND = RATE * 2
MIN_SECONDS = 0.6
WEAK_WORD_SCORE = 60  # Azure accuracy below this = word worth practising
MAX_WEAK_WORDS = 3
FRAME = int(RATE * 0.02)  # 20 ms
SILENCE_PAD = int(RATE * 0.2)
VIETNAMESE_CHARS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.IGNORECASE)


class LearnerTurn:
    """Mic audio and transcript of the learner's current turn (reset when the tutor starts answering)."""

    def __init__(self) -> None:
        self._audio = bytearray()
        self._text: list[str] = []

    def add_audio(self, pcm: bytes) -> None:
        self._audio += pcm
        # Keep only the most recent audio; the turn itself is at most azure.MAX_SECONDS long.
        overflow = len(self._audio) - BYTES_PER_SECOND * (azure.MAX_SECONDS + 10)
        if overflow > 0:
            del self._audio[:overflow]

    def add_text(self, fragment: str) -> None:
        self._text.append(fragment)

    def take(self) -> tuple[bytes, str] | None:
        """End the turn: return (audio, transcript) if the learner said something, and start a new turn."""
        text = "".join(self._text).strip()
        audio = bytes(self._audio)
        self._audio.clear()
        self._text.clear()
        return (audio, text) if text else None


def trim_silence(pcm: bytes) -> bytes:
    """Cut leading / trailing silence (the buffer also holds pauses and time while the tutor spoke)."""
    x = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype="<i2").astype(np.float32)
    n = len(x) // FRAME
    if n == 0:
        return b""
    rms = np.sqrt((x[: n * FRAME].reshape(n, FRAME) ** 2).mean(axis=1))
    loud = np.nonzero(rms > max(300.0, rms.max() * 0.08))[0]
    if len(loud) == 0:
        return b""
    start = max(0, loud[0] * FRAME - SILENCE_PAD)
    end = min(len(x), (loud[-1] + 1) * FRAME + SILENCE_PAD)
    return pcm[start * 2 : end * 2]


def reference_text(transcript: str) -> str | None:
    """Text Azure should score against, or None when the turn can't be assessed fairly (Vietnamese, noise)."""
    if VIETNAMESE_CHARS.search(transcript):
        return None  # mixed Vietnamese/English: English-only scoring would be wrong
    text = re.sub(r"<[^>]*>", " ", transcript)  # transcription tags such as <noise>
    text = re.sub(r"[^A-Za-z0-9'.,?!\- ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if re.search(r"[A-Za-z]{2,}", text) else None


@dataclass
class TurnPronunciation:
    text: str
    score: float
    accuracy: float
    fluency: float | None
    prosody: float | None
    weak_words: list[dict]
    engine: str = "azure"  # [{"word", "score", "error_type"}]

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "score": round(self.score),
            "accuracy": round(self.accuracy),
            "fluency": None if self.fluency is None else round(self.fluency),
            "prosody": None if self.prosody is None else round(self.prosody),
            "weak_words": self.weak_words,
            "engine": self.engine,
        }


async def assess_turn(pcm: bytes, transcript: str) -> TurnPronunciation | None:
    """Score one learner turn on its real audio. None = not assessable (too short / long, mixed language)."""
    text = reference_text(transcript)
    if text is None:
        return None
    speech = trim_silence(pcm)
    if not MIN_SECONDS * BYTES_PER_SECOND <= len(speech) <= azure.MAX_SECONDS * BYTES_PER_SECOND:
        return None
    result = await assessment.assess(speech, text)
    weak = [
        {"word": w.word, "score": round(w.score), "error_type": w.error_type}
        for w in result.words
        if w.error_type == "Mispronunciation" or (w.error_type == "None" and w.score < WEAK_WORD_SCORE)
    ]
    weak.sort(key=lambda w: w["score"])
    return TurnPronunciation(
        text=text,
        score=result.pron_score,
        accuracy=result.accuracy,
        fluency=result.fluency,
        prosody=result.prosody,
        engine=result.engine,
        weak_words=weak[:MAX_WEAK_WORDS],
    )


def tutor_note(p: TurnPronunciation) -> str:
    """Compact, factual message for the tutor model (see PRONUNCIATION_WITH_DATA in tutor.py)."""
    weak = ", ".join(f"'{w['word']}' {w['score']}/100" for w in p.weak_words) or "none"
    fluency = "" if p.fluency is None else f", fluency {round(p.fluency)}"
    prosody = "" if p.prosody is None else f", intonation {round(p.prosody)}"
    source = "estimate from a phoneme model" if p.engine == "local" else "Azure"
    return (
        f'[Pronunciation data] Learner\'s last turn "{p.text}": overall {round(p.score)}/100 '
        f"(accuracy {round(p.accuracy)}{fluency}{prosody}; {source}). Weak words: {weak}. "
        "Use this in your next reply only if it helps; do not answer this message on its own."
    )


ResultHandler = Callable[[int, TurnPronunciation], Awaitable[None]]
NoteSender = Callable[[str], Awaitable[None]]


class PronunciationCoach:
    """Per-session glue: collects each learner turn, scores it in the background after the tutor has answered
    it, and hands the result to the UI (`on_result`) and to the tutor model (`send_note`), which uses it in a
    later reply.

    Notes are only sent while the tutor is NOT generating: new client content interrupts a Live model's
    current answer, so a note that arrives mid-answer waits for the end of that answer.
    """

    def __init__(
        self,
        enabled: bool,
        on_result: ResultHandler,
        send_note: NoteSender,
        allow: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        self.enabled = enabled
        self._allow = allow  # per-turn quota check (daily limit)
        self._on_result = on_result
        self._send_note = send_note
        self._turn = LearnerTurn()
        self._tutor_speaking = False
        self._pending: list[str] = []
        self._tasks: set[asyncio.Task] = set()

    def learner_audio(self, pcm: bytes) -> None:
        if self.enabled:
            self._turn.add_audio(pcm)

    def learner_text(self, fragment: str) -> None:
        if self.enabled:
            self._turn.add_text(fragment)

    def tutor_output(self) -> None:
        """Tutor is answering (any output chunk)."""
        self._tutor_speaking = True

    async def tutor_done(self, turn_index: int) -> None:
        """Tutor finished (or was interrupted). The learner turn it answered is complete now — the input
        transcript often arrives after the answer has started — so score it, and deliver waiting notes."""
        self._tutor_speaking = False
        turn = self._turn.take() if self.enabled else None
        if turn and (self._allow is None or await self._allow()):
            task = asyncio.create_task(self._assess(turn_index, *turn))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        pending, self._pending = self._pending, []
        for note in pending:
            await self._send_note(note)

    def close(self) -> None:
        for task in self._tasks:
            task.cancel()

    async def _assess(self, turn_index: int, pcm: bytes, transcript: str) -> None:
        try:
            result = await assess_turn(pcm, transcript)
        except azure.PronunciationError as e:
            log.info("turn pronunciation skipped: %s", e)
            return
        except Exception:
            log.exception("turn pronunciation failed")
            return
        if result is None:
            return
        await self._on_result(turn_index, result)
        note = tutor_note(result)
        if self._tutor_speaking:
            self._pending.append(note)
        else:
            await self._send_note(note)
