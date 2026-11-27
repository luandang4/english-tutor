"""Local phoneme scoring (alignment + GOP maths on synthetic logits) and engine selection. No model needed."""

import numpy as np
import pytest

from app.services.speech import assessment, azure, phoneme

VOCAB = {"<pad>": 0, "k": 1, "æ": 2, "t": 3, "ɾ": 4}


def _model() -> phoneme._Model:
    m = phoneme._Model(session=None, vocab=VOCAB, inv={i: t for t, i in VOCAB.items()}, blank=0, variants={})
    m.variants = {3: [4], 4: [3]}  # t ~ ɾ accepted
    return m


def _logits(frames: list[int], confidence: float = 8.0) -> np.ndarray:
    out = np.zeros((len(frames), len(VOCAB)))
    for t, tok in enumerate(frames):
        out[t, tok] = confidence
    return out


def test_ctc_alignment_assigns_frames_to_each_phone() -> None:
    logits = _logits([0, 1, 1, 0, 2, 2, 0, 3, 0])  # _ k k _ æ æ _ t _
    logp = logits - np.log(np.exp(logits).sum(-1, keepdims=True))
    assert phoneme.ctc_align(logp, [1, 2, 3], blank=0) == [[2, 1], [5, 4], [7]]


def test_clear_speech_scores_high_and_a_missing_phone_scores_low() -> None:
    words = [("cat", [1, 2, 3])]
    good = phoneme.score_from_logits(_logits([0, 1, 1, 0, 2, 2, 0, 3, 0]), words, _model())
    assert good.engine == "local" and good.fluency is None
    assert good.words[0].score > 90 and good.words[0].error_type == "None"

    # final /t/ dropped (heard "ca"): the /t/ phoneme gets almost nothing
    bad = phoneme.score_from_logits(_logits([0, 1, 1, 0, 2, 2, 2, 0, 0]), words, _model())
    t_score = bad.words[0].phonemes[2]["score"]
    assert t_score < 20 and bad.words[0].score < good.words[0].score


def test_accent_variant_is_accepted() -> None:
    words = [("cat", [1, 2, 3])]
    flap = phoneme.score_from_logits(_logits([0, 1, 1, 0, 2, 2, 0, 4, 0]), words, _model())  # t said as ɾ
    assert flap.words[0].phonemes[2]["score"] > 90


async def test_auto_falls_back_to_local_only_when_azure_is_unavailable(monkeypatch) -> None:
    from app.core.config import get_settings

    pcm = b"\0" * 32000
    local = azure.Assessment("", 70, 70, None, 100, None, [], engine="local")
    calls = []

    async def fake_local(p: bytes, t: str) -> azure.Assessment:
        calls.append("local")
        return local

    monkeypatch.setattr(get_settings(), "pronunciation_engine", "auto")
    monkeypatch.setattr(phoneme, "available", lambda: True)
    monkeypatch.setattr(phoneme, "assess", fake_local)

    async def azure_down(p: bytes, t: str) -> azure.Assessment:
        raise azure.PronunciationError("quota", service_issue=True)

    monkeypatch.setattr(azure, "assess", azure_down)
    assert (await assessment.assess(pcm, "cat")).engine == "local"

    async def no_speech(p: bytes, t: str) -> azure.Assessment:
        raise azure.PronunciationError("no speech")  # a problem with the recording, not with Azure

    monkeypatch.setattr(azure, "assess", no_speech)
    with pytest.raises(azure.PronunciationError):
        await assessment.assess(pcm, "cat")
    assert calls == ["local"]
