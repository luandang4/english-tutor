"""Tutor persona and Gemini Live session config for voice conversation.

Provider-specific settings live here so the voice backend can be swapped
(e.g. OpenAI Realtime, LiveKit cascade) without touching the web layer.
"""

from dataclasses import dataclass

from google.genai import types

from app.core.config import get_settings
from app.core.constants import LEVELS
from app.services.conversation.tutor import system_prompt

INPUT_RATE = 16_000  # browser mic -> Gemini (PCM16 mono)
OUTPUT_RATE = 24_000  # Gemini -> browser (PCM16 mono)

SCENARIOS: dict[str, dict[str, str]] = {
    "free_talk": {
        "label": "Nói chuyện tự do",
        "ai": "Free conversation. Find out what the learner likes and talk about it.",
    },
    "coffee_shop": {
        "label": "Gọi đồ ở quán cà phê",
        "ai": "Role-play: you are a barista, the learner orders drinks and snacks.",
    },
    "job_interview": {
        "label": "Phỏng vấn xin việc",
        "ai": "Role-play: you are an interviewer for a software engineer job.",
    },
    "travel": {
        "label": "Nhận phòng khách sạn",
        "ai": "Role-play: you are a hotel receptionist; the learner checks in and asks about the city.",
    },
    "doctor": {
        "label": "Đi khám bác sĩ",
        "ai": "Role-play: you are a doctor; the learner describes symptoms.",
    },
    "small_talk": {
        "label": "Làm quen đồng nghiệp",
        "ai": "Small talk with a new colleague at the office.",
    },
}

VOICE = "Kore"  # the one tutor voice used everywhere

OPENING_PROMPT = "(The learner just joined. Greet them briefly and start the lesson.)"


@dataclass
class LiveSettings:
    level: str = "B1"
    scenario: str = "free_talk"

    @classmethod
    def from_dict(cls, d: dict) -> "LiveSettings":
        return cls(
            level=d.get("level") if d.get("level") in LEVELS else "B1",
            scenario=d.get("scenario") if d.get("scenario") in SCENARIOS else "free_talk",
        )


def live_config(
    s: LiveSettings, resume_handle: str | None = None, pronunciation_data: bool = False
) -> types.LiveConnectConfig:
    silence_ms = get_settings().live_end_of_speech_ms
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=system_prompt(s.level, SCENARIOS[s.scenario]["ai"], pronunciation_data),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE))
        ),
        # Learners pause mid-sentence while searching for words: wait longer before treating silence as the end
        # of their turn, so Emma doesn't cut them off.
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                silence_duration_ms=silence_ms,
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # Keep long lessons under the context limit (and cost) — drops oldest turns.
        context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
        # Lets us reconnect after GoAway without losing the conversation.
        session_resumption=types.SessionResumptionConfig(handle=resume_handle),
    )
