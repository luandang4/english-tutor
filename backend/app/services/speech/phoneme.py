"""Local pronunciation scoring with a phoneme-recognition model — free alternative / fallback to Azure.

Model: facebook/wav2vec2-lv-60-espeak-cv-ft (Apache-2.0), exported to ONNX and int8-quantized (MatMul only):
`scripts/export_phoneme_model.py`. It outputs espeak IPA phonemes per 20 ms frame.

Scoring (GOP-style):
1. espeak turns the reference text into the expected phoneme sequence (same espeak-ng as Kokoro),
2. CTC Viterbi forced alignment assigns audio frames to each expected phoneme,
3. phoneme score = mean posterior of that phoneme (or an accepted accent variant) over its frames,
   ignoring the CTC blank; word score = mean of its phonemes.

Scores are an *estimate* (the model learned native speech; Azure is trained for learner assessment).
The ONNX session is loaded on first use and released after `PHONEME_IDLE_UNLOAD_SECONDS` without use (~800 MB).
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.services.speech.azure import Assessment, PronunciationError, WordScore

log = logging.getLogger(__name__)

WEAK_WORD = 60  # below this a word is reported as mispronounced (same threshold the tutor uses)

# Accent / reduction variants accepted as correct for an expected phoneme (US/UK and connected speech).
_VARIANT_GROUPS = [
    {"ɔː", "ɑː", "ɔ", "ɑ"},
    {"ə", "ʌ", "ɐ", "ᵻ"},
    {"ɚ", "ɜː", "ɜ"},
    {"t", "ɾ"},
    {"d", "ɾ"},
    {"oʊ", "o", "oː", "əʊ"},
    {"ɛ", "e"},
    {"ɪ", "ᵻ"},
]


@dataclass
class _Model:
    session: Any
    vocab: dict[str, int]
    inv: dict[int, str]
    blank: int
    variants: dict[int, list[int]]


_model: _Model | None = None
_last_used = 0.0
_load_lock = threading.Lock()
_unloader: asyncio.Task | None = None


# ---------- model lifecycle ----------
def available() -> bool:
    s = get_settings()
    return s.phoneme_model_path.exists() and s.phoneme_vocab_path.exists()


def _load() -> _Model:
    global _model
    with _load_lock:
        if _model is None:
            import onnxruntime as ort

            s = get_settings()
            if not available():
                raise PronunciationError("Chưa có model chấm phát âm local (scripts/export_phoneme_model.py).")
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = s.phoneme_threads
            session = ort.InferenceSession(str(s.phoneme_model_path), opts, providers=["CPUExecutionProvider"])
            vocab = json.loads(s.phoneme_vocab_path.read_text())
            variants = {}
            for group in _VARIANT_GROUPS:
                ids = [vocab[p] for p in group if p in vocab]
                for i in ids:
                    variants.setdefault(i, []).extend(j for j in ids if j != i)
            _model = _Model(session, vocab, {i: t for t, i in vocab.items()}, vocab["<pad>"], variants)
            log.info("phoneme model loaded")
        return _model


def unload_if_idle() -> bool:
    global _model
    with _load_lock:
        idle = time.monotonic() - _last_used
        if _model is not None and idle >= get_settings().phoneme_idle_unload_seconds:
            _model = None
            log.info("phoneme model unloaded after %.0fs idle", idle)
            return True
    return False


async def _unload_loop() -> None:
    while _model is not None:
        await asyncio.sleep(60)
        unload_if_idle()


def _schedule_unload() -> None:
    global _unloader
    if _unloader is None or _unloader.done():
        _unloader = asyncio.get_running_loop().create_task(_unload_loop(), name="phoneme-unload")


# ---------- text -> expected phonemes ----------
def _phonemize(text: str) -> str:
    import espeakng_loader
    from kokoro_onnx.tokenizer import _espeak_lock  # espeak-ng is process-global; Kokoro uses it too
    from phonemizer import phonemize
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    from phonemizer.separator import Separator

    with _espeak_lock:
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        return phonemize(
            text,
            language="en-us",
            backend="espeak",
            separator=Separator(phone=" ", word=" | "),
            strip=True,
            with_stress=False,
        )


def expected_phonemes(text: str, vocab: dict[str, int]) -> list[tuple[str, list[int]]]:
    """[(word, model token ids)] — espeak symbols split into model tokens by longest match."""
    words = [w.strip('.,!?;:"()') for w in text.split()]
    words = [w for w in words if w]
    chunks = _phonemize(" ".join(words)).split(" | ")
    out = []
    for word, chunk in zip(words, chunks, strict=False):
        ids = []
        for ph in chunk.split():
            i = 0
            while i < len(ph):
                for j in range(len(ph), i, -1):
                    if ph[i:j] in vocab:
                        ids.append(vocab[ph[i:j]])
                        i = j
                        break
                else:
                    i += 1  # symbol unknown to the model
        out.append((word, ids))
    return out


# ---------- scoring ----------
def ctc_align(logp: np.ndarray, targets: list[int], blank: int) -> list[list[int]]:
    """CTC Viterbi forced alignment: the frames assigned to each target token."""
    T, S = logp.shape[0], 2 * len(targets) + 1
    if not targets or T == 0:
        return [[] for _ in targets]
    ext = [blank if s % 2 == 0 else targets[s // 2] for s in range(S)]
    dp = np.full((T, S), -np.inf)
    bp = np.zeros((T, S), dtype=np.int32)
    dp[0, 0] = logp[0, ext[0]]
    dp[0, 1] = logp[0, ext[1]]
    for t in range(1, T):
        prev = dp[t - 1]
        stay = prev
        step = np.concatenate([[-np.inf], prev[:-1]])
        skip = np.concatenate([[-np.inf, -np.inf], prev[:-2]])
        can_skip = np.array([s >= 2 and ext[s] != blank and ext[s] != ext[s - 2] for s in range(S)])
        skip = np.where(can_skip, skip, -np.inf)
        stacked = np.stack([stay, step, skip])
        arg = stacked.argmax(0)
        dp[t] = stacked.max(0) + logp[t, ext]
        bp[t] = np.arange(S) - arg
    s = S - 1 if dp[T - 1, S - 1] >= dp[T - 1, S - 2] else S - 2
    frames: list[list[int]] = [[] for _ in targets]
    for t in range(T - 1, -1, -1):
        if s % 2 == 1:
            frames[s // 2].append(t)
        s = bp[t, s]
    return frames


def score_from_logits(logits: np.ndarray, words: list[tuple[str, list[int]]], model: _Model) -> Assessment:
    logits = logits - logits.max(-1, keepdims=True)
    logp = logits - np.log(np.exp(logits).sum(-1, keepdims=True))
    probs = np.exp(logp)
    flat = [i for _, ids in words for i in ids]
    frames = ctc_align(logp, flat, model.blank)
    k = 0
    results: list[WordScore] = []
    for word, ids in words:
        phonemes = []
        for tid in ids:
            fr = frames[k]
            k += 1
            if not fr:
                phonemes.append({"phoneme": model.inv[tid], "score": 0.0})
                continue
            accepted = [tid, *model.variants.get(tid, [])]
            non_blank = 1 - probs[fr, model.blank] + 1e-6
            p = probs[np.ix_(fr, accepted)].sum(1) / non_blank
            phonemes.append({"phoneme": model.inv[tid], "score": round(float(min(1.0, p.mean())) * 100, 1)})
        score = float(np.mean([p["score"] for p in phonemes])) if phonemes else 0.0
        error = "Mispronunciation" if score < WEAK_WORD else "None"
        results.append(WordScore(word=word, score=round(score, 1), error_type=error, phonemes=phonemes))
    accuracy = float(np.mean([w.score for w in results])) if results else 0.0
    completeness = 100.0 * sum(w.score >= 30 for w in results) / len(results) if results else 0.0
    return Assessment(
        recognized_text="",
        pron_score=round(accuracy, 1),
        accuracy=round(accuracy, 1),
        fluency=None,
        completeness=round(completeness, 1),
        prosody=None,
        words=results,
        engine="local",
    )


def _assess_sync(pcm16: bytes, reference_text: str) -> Assessment:
    global _last_used
    model = _load()
    _last_used = time.monotonic()
    x = np.frombuffer(pcm16[: len(pcm16) - len(pcm16) % 2], dtype="<i2").astype(np.float32) / 32768
    x = (x - x.mean()) / (x.std() + 1e-7)
    logits = model.session.run(None, {"input_values": x[None, :]})[0][0]
    words = expected_phonemes(reference_text, model.vocab)
    if not any(ids for _, ids in words):
        raise PronunciationError("Không tách được âm của câu mẫu.")
    _last_used = time.monotonic()
    return score_from_logits(logits, words, model)


async def assess(pcm16: bytes, reference_text: str) -> Assessment:
    result = await asyncio.to_thread(_assess_sync, pcm16, reference_text)
    _schedule_unload()
    return result
