"""Pronunciation audio for words and example sentences — free sources only, no paid AI.

Source chain (first one that works wins; result cached on disk):
- single words / short phrases: Google Translate voice (gTTS, consistent dictionary-style reading)
  -> human recording (Wiktionary / Commons; volunteer recordings, intonation varies) -> Kokoro-82M
- sentences: Kokoro-82M (local, natural sentence prosody) -> Google Translate voice

Kokoro alone mis-stresses isolated words (it is trained on sentences), hence the word chain.
Sources: en.wiktionary.org API · github.com/pndurette/gTTS · github.com/thewh1teagle/kokoro-onnx
"""

import asyncio
import hashlib
import io
import logging
import re
import time
import wave
from collections.abc import Awaitable, Callable

import httpx
import numpy as np

from app.core.config import get_settings
from app.services.speech.audio_store import cleanup, get_store

log = logging.getLogger(__name__)
CACHE_VERSION = "v2"
FADE_SECONDS = 0.01
PAD_SECONDS = 0.08
SHORT_MAX_WORDS = 3
FALLBACK_RETRY_SECONDS = 600  # cached fallback audio: retry the preferred source after this
MEDIA = {".mp3": "audio/mpeg", ".wav": "audio/wav"}

_engine = None
_kokoro_lock = asyncio.Lock()  # one synthesis at a time: ONNX session is CPU-bound


class TTSError(RuntimeError):
    pass


# ---------- Kokoro (local) ----------
def _load_kokoro():  # noqa: ANN202
    global _engine
    if _engine is None:
        s = get_settings()
        if not (s.tts_model_path.exists() and s.tts_voices_path.exists()):
            raise TTSError("Chưa tải model Kokoro. Chạy `make tts-model`.")
        from kokoro_onnx import Kokoro

        _engine = Kokoro(str(s.tts_model_path), str(s.tts_voices_path))
        log.info("Kokoro TTS loaded")
    return _engine


def _to_wav(samples: np.ndarray, rate: int) -> bytes:
    """Float samples -> 16-bit WAV with short fades and silence padding (no clicks at start/end)."""
    x = np.asarray(samples, dtype=np.float32)
    n = min(int(rate * FADE_SECONDS), len(x) // 2)
    if n:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    pad = np.zeros(int(rate * PAD_SECONDS), dtype=np.float32)
    pcm = (np.clip(np.concatenate([pad, x, pad]), -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _kokoro_sync(text: str) -> bytes:
    s = get_settings()
    if not re.search(r"[.!?]$", text):
        text += "."  # a full stop gives a natural falling (declarative) contour
    samples, rate = _load_kokoro().create(text, voice=s.tts_voice, speed=s.tts_speed, lang="en-us")
    return _to_wav(samples, rate)


async def _kokoro(text: str) -> tuple[bytes, str]:
    async with _kokoro_lock:
        return await asyncio.to_thread(_kokoro_sync, text), ".wav"


# ---------- human recording (Wiktionary / Wikimedia Commons, CC-licensed) ----------
WIKI_HEADERS = {"User-Agent": "EnglishTutor/0.2 (personal learning app)"}
AUDIO_EXT = (".ogg", ".oga", ".mp3", ".wav", ".flac", ".opus")


async def _dictionary(text: str) -> tuple[bytes, str]:
    """Real speaker recording of a single word, preferring US then UK English (MP3 transcode from Commons)."""
    word = text.strip().lower()
    if " " in word:
        raise TTSError("phrases have no recordings")
    async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=WIKI_HEADERS) as client:
        page = await client.get(
            "https://en.wiktionary.org/w/api.php",
            params={"action": "parse", "page": word, "prop": "images", "format": "json", "formatversion": 2},
        )
        files = [
            f
            for f in page.json().get("parse", {}).get("images", [])
            if f.lower().startswith("en-") and f.lower().endswith(AUDIO_EXT)
        ]
        if not files:
            raise TTSError("no recording")
        files.sort(key=lambda f: (not f.lower().startswith("en-us"), not f.lower().startswith(("en-uk", "en-gb"))))
        info = await client.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "titles": f"File:{files[0]}",
                "prop": "videoinfo",
                "viprop": "url|derivatives",
                "format": "json",
                "formatversion": 2,
            },
        )
        vi = (info.json()["query"]["pages"][0].get("videoinfo") or [{}])[0]
        mp3 = [d["src"] for d in vi.get("derivatives", []) if d.get("type", "").startswith("audio/mpeg")]
        if not mp3:
            raise TTSError("no mp3 transcode")
        audio = await client.get(mp3[0])
        if audio.status_code != 200 or not audio.content:
            raise TTSError("recording download failed")
        return audio.content, ".mp3"


# ---------- Google Translate voice (gTTS) ----------
def _google_sync(text: str) -> bytes:
    from gtts import gTTS

    buf = io.BytesIO()
    gTTS(text, lang="en", tld="com").write_to_fp(buf)
    return buf.getvalue()


async def _google(text: str) -> tuple[bytes, str]:
    return await asyncio.to_thread(_google_sync, text), ".mp3"


SOURCES: dict[str, Callable[[str], Awaitable[tuple[bytes, str]]]] = {
    "dictionary": _dictionary,
    "google": _google,
    "kokoro": _kokoro,
}


SOURCE_CHOICES = tuple(SOURCES)


def _chain(text: str, preferred: str | None = None) -> list[str]:
    """Default chain for the text, or the learner's chosen source first with the default chain as fallback."""
    s = get_settings()
    short = len(text.split()) <= SHORT_MAX_WORDS and not re.search(r"[.!?,;]", text)
    default = s.tts_word_sources if short else s.tts_sentence_sources
    if preferred in SOURCES:
        return [preferred, *(n for n in default if n != preferred)]
    return default


def _parse_name(name: str) -> tuple[str, str] | None:
    """'{key}.{source}{ext}' -> (source, media type)."""
    parts = name.split(".")
    if len(parts) != 3:
        return None
    media = MEDIA.get(f".{parts[2]}")
    return (parts[1], media) if media else None


async def synthesize(text: str, preferred: str | None = None) -> tuple[bytes, str, str]:
    """Return (audio bytes, media type, source name). `preferred` = learner-chosen source (falls back on failure)."""
    store = get_store()
    chain = _chain(text, preferred)
    key = hashlib.sha256(f"{CACHE_VERSION}|{','.join(chain)}|{text}".encode()).hexdigest()[:32]
    stale = None
    for cached in await store.find(key):
        parsed = _parse_name(cached.name)
        if parsed is None or parsed[0] not in chain:
            continue
        source, media = parsed
        # A fallback result (preferred source was down) is retried later instead of being kept forever.
        if source == chain[0] or time.time() - cached.mtime < FALLBACK_RETRY_SECONDS:
            return await store.read(cached.name), media, source
        stale = (cached.name, media, source)
        chain = chain[: chain.index(source)]  # only sources better than the cached one
        break

    for name in chain:
        try:
            audio, ext = await SOURCES[name](text)
        except Exception as e:  # noqa: BLE001 — try the next source
            log.warning("TTS source %s failed for %r: %s", name, text[:40], e)
            continue
        await store.write(f"{key}.{name}{ext}", audio)
        if stale:
            await store.delete(stale[0])
        return audio, MEDIA[ext], name
    if stale:  # preferred source still down: keep serving the fallback, retry again later
        await store.touch(stale[0])
        return await store.read(stale[0]), stale[1], stale[2]
    raise TTSError("Không tạo được âm thanh.")


async def cache_maintenance(interval_seconds: int = 3600) -> None:
    """Background loop: keep the audio cache (local folder or S3) within the age / size limits."""
    while True:
        s = get_settings()
        try:
            n = await cleanup(get_store(), s.tts_cache_max_days, s.tts_cache_max_mb * 1024 * 1024)
            if n:
                log.info("TTS cache cleanup removed %d file(s)", n)
        except Exception:
            log.exception("TTS cache cleanup failed")
        await asyncio.sleep(interval_seconds)


async def prefetch(texts: list[str]) -> None:
    """Fill the cache in the background (e.g. all words of a new lesson) so playback is instant."""
    for text in texts:
        try:
            await synthesize(text)
        except Exception as e:  # noqa: BLE001
            log.info("TTS prefetch skipped %r: %s", text[:40], e)


async def warm_up() -> None:
    """Load Kokoro in the background so the first sentence plays quickly."""
    if "kokoro" not in {*get_settings().tts_word_sources, *get_settings().tts_sentence_sources}:
        return
    if not get_settings().tts_model_path.exists():
        log.warning("Kokoro model missing — run `make tts-model` (other sources still work)")
        return
    try:
        await _kokoro("Hi")
    except Exception:
        log.exception("Kokoro warm-up failed")
