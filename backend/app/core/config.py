"""Application settings, loaded from environment variables and the project-root `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # --- providers -------------------------------------------------------
    # Vendor split (see docs/TECHSTACK.md): Azure = pronunciation scoring only; Gemini = everything else.
    gemini_api_key: str
    azure_speech_key: str = ""
    azure_speech_region: str = "southeastasia"

    # Gemini models, tried in order (fallback on quota / overload / timeout).
    live_model: str = "gemini-3.8-live"
    content_models: list[str] = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
    grading_models: list[str] = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
    writing_models: list[str] = ["gemini-3.5-flash", "gemini-3.8-flash"]
    ai_timeout_seconds: float = 120.0

    # Pronunciation audio (free sources, see services/speech/tts.py). Order = priority.
    tts_word_sources: list[str] = ["google", "dictionary", "kokoro"]
    tts_sentence_sources: list[str] = ["kokoro", "google"]
    tts_prefetch: bool = True  # cache word audio as soon as a vocabulary lesson is generated
    # Kokoro-82M (local, offline)
    tts_model_path: Path = DATA_DIR / "models" / "kokoro-v1.0.onnx"
    tts_voices_path: Path = DATA_DIR / "models" / "voices-v1.0.bin"
    tts_voice: str = "af_heart"
    tts_speed: float = 0.95

    # --- storage ---------------------------------------------------------
    database_url: str = Field(default=f"sqlite+aiosqlite:///{DATA_DIR / 'app.db'}")
    run_migrations_on_startup: bool = True

    # Day boundaries for streaks / activity charts.
    timezone: str = "Asia/Ho_Chi_Minh"

    # --- accounts ---------------------------------------------------------
    allow_registration: bool = True
    session_days: int = 30
    session_cookie: str = "et_session"
    cookie_secure: bool = False  # set true when served over HTTPS

    # --- web -------------------------------------------------------------
    frontend_dist: Path = ROOT_DIR / "frontend" / "dist"
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- live conversation limits -----------------------------------------
    max_concurrent_live_sessions: int = 2
    max_live_session_minutes: int = 30

    @property
    def azure_enabled(self) -> bool:
        return bool(self.azure_speech_key and self.azure_speech_region)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
