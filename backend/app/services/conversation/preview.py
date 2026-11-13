"""Short sample of a tutor voice (Gemini Live) so the learner can compare voices before starting a lesson.

The sample is generated once per voice and cached on disk (shared by all users), so it costs one tiny
Live call per voice, not one per click.
"""

import asyncio
import io
import wave

from google.genai import types

from app.core.config import get_settings
from app.services.ai.client import get_genai_client
from app.services.conversation.live import OUTPUT_RATE, VOICES
from app.services.speech.tts import CACHE_DIR

PREVIEW_TEXT = "Hi, I'm Emma, your English tutor. Let's practice together today!"
PREVIEW_TIMEOUT = 25
_locks = {v: asyncio.Lock() for v in VOICES}


class PreviewError(RuntimeError):
    pass


def _wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(OUTPUT_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


async def _generate(voice: str) -> bytes:
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))
        ),
    )
    chunks: list[bytes] = []
    async with get_genai_client().aio.live.connect(model=get_settings().live_model, config=config) as session:
        await session.send_client_content(
            turns=types.Content(
                role="user", parts=[types.Part(text=f"Say exactly this sentence, nothing else: {PREVIEW_TEXT}")]
            ),
            turn_complete=True,
        )
        async for m in session.receive():
            if m.data:
                chunks.append(m.data)
            if m.server_content and m.server_content.turn_complete:
                break
    if not chunks:
        raise PreviewError("Gemini không trả về âm thanh.")
    return _wav(b"".join(chunks))


async def voice_preview(voice: str) -> bytes:
    """WAV sample of a Gemini voice (cached)."""
    if voice not in VOICES:
        raise PreviewError("Giọng không hợp lệ.")
    path = CACHE_DIR / f"voice-preview-{voice}.gemini.wav"
    async with _locks[voice]:
        if path.exists():
            return await asyncio.to_thread(path.read_bytes)
        try:
            async with asyncio.timeout(PREVIEW_TIMEOUT):
                audio = await _generate(voice)
        except TimeoutError as e:
            raise PreviewError("Gemini phản hồi quá lâu, thử lại sau.") from e
        except PreviewError:
            raise
        except Exception as e:
            raise PreviewError(f"Không tạo được giọng mẫu: {e}") from e
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, audio)
        return audio
