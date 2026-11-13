"""Tutor prompt per level and pronunciation evidence for voice conversations (no network)."""

import asyncio

import numpy as np
import pytest

from app.core.constants import LEVELS
from app.services.conversation import pronunciation as pron
from app.services.conversation.live import SCENARIOS, LiveSettings, live_config
from app.services.conversation.tutor import LEVEL_POLICY, system_prompt


def test_every_level_has_a_policy() -> None:
    assert set(LEVEL_POLICY) == set(LEVELS)


@pytest.mark.parametrize("level", list(LEVELS))
def test_prompt_locks_level_and_requires_correction(level: str) -> None:
    prompt = system_prompt(level, SCENARIOS["free_talk"]["ai"], pronunciation_data=True)
    assert f"CEFR {level}" in prompt
    assert "locked" in prompt
    assert "does NOT change this rule" in prompt
    assert "ignore a real error" in prompt
    assert "[Pronunciation data]" in prompt


def test_enhancement_only_for_advanced_levels() -> None:
    for level in ("A1", "A2", "B1"):
        assert "No enhancement at this level" in system_prompt(level, "x", False)
    for level in ("B2", "C1"):
        assert "Enhancement (this level)" in system_prompt(level, "x", False)


def test_without_azure_the_tutor_must_not_judge_pronunciation() -> None:
    prompt = system_prompt("B1", "x", pronunciation_data=False)
    assert "not available" in prompt
    assert "[Pronunciation data]" not in prompt


def test_live_config_waits_for_the_learner_to_finish() -> None:
    cfg = live_config(LiveSettings(level="A1"), pronunciation_data=True)
    vad = cfg.realtime_input_config.automatic_activity_detection
    assert vad.silence_duration_ms >= 1000
    assert "CEFR A1" in cfg.system_instruction


def test_reference_text_skips_mixed_vietnamese_and_noise() -> None:
    assert pron.reference_text("Today I go... à, đi siêu thị") is None
    assert pron.reference_text("<noise>") is None
    assert pron.reference_text(" Yesterday I go shopping. ") == "Yesterday I go shopping."


def _tone(seconds: float, amp: int = 8000) -> bytes:
    t = np.arange(int(pron.RATE * seconds)) / pron.RATE
    return (np.sin(2 * np.pi * 220 * t) * amp).astype("<i2").tobytes()


def test_trim_silence_keeps_only_speech() -> None:
    silence = b"\x00\x00" * pron.RATE  # 1 s
    trimmed = pron.trim_silence(silence + _tone(1.0) + silence)
    assert 1.0 <= len(trimmed) / pron.BYTES_PER_SECOND <= 1.5
    assert pron.trim_silence(silence) == b""


def test_learner_turn_needs_speech_text() -> None:
    turn = pron.LearnerTurn()
    turn.add_audio(_tone(0.5))
    assert turn.take() is None  # audio without a transcript (noise) is not a turn
    turn.add_audio(_tone(0.5))
    turn.add_text("Hello ")
    turn.add_text("there")
    audio, text = turn.take()
    assert text == "Hello there" and len(audio) == pron.BYTES_PER_SECOND // 2
    assert turn.take() is None


def _result(score: float = 70) -> pron.TurnPronunciation:
    return pron.TurnPronunciation(
        text="I went to the supermarket",
        score=score,
        accuracy=72,
        fluency=80,
        prosody=None,
        weak_words=[{"word": "supermarket", "score": 41, "error_type": "Mispronunciation"}],
    )


def test_tutor_note_is_factual_and_compact() -> None:
    note = pron.tutor_note(_result())
    assert note.startswith("[Pronunciation data]")
    assert "'supermarket' 41/100" in note


async def test_coach_scores_turn_after_tutor_answer_and_holds_note_while_tutor_speaks(monkeypatch) -> None:
    gate = asyncio.Event()

    async def fake_assess(pcm: bytes, transcript: str) -> pron.TurnPronunciation:
        await gate.wait()
        return _result()

    monkeypatch.setattr(pron, "assess_turn", fake_assess)
    results, notes = [], []

    async def on_result(index: int, r: pron.TurnPronunciation) -> None:
        results.append(index)

    async def send_note(note: str) -> None:
        notes.append(note)

    coach = pron.PronunciationCoach(True, on_result, send_note)
    coach.learner_audio(_tone(1.0))
    coach.learner_text("I went to the supermarket")
    coach.tutor_output()
    await coach.tutor_done(turn_index=1)  # answer finished -> learner turn is scored in the background

    coach.tutor_output()  # next answer already playing when Azure returns
    gate.set()
    await asyncio.sleep(0.01)
    assert results == [1]
    assert notes == []  # would interrupt the current answer
    await coach.tutor_done(turn_index=3)
    assert len(notes) == 1


async def test_coach_disabled_does_nothing(monkeypatch) -> None:
    called = False

    async def fake_assess(pcm: bytes, transcript: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(pron, "assess_turn", fake_assess)

    async def noop(*_: object) -> None:
        pass

    coach = pron.PronunciationCoach(False, noop, noop)
    coach.learner_audio(_tone(1.0))
    coach.learner_text("Hello")
    await coach.tutor_done(0)
    await asyncio.sleep(0)
    assert not called
