"""Thin Gemini wrapper: structured JSON generation with a model fallback chain.

Every non-speech AI task goes through here (vendor rule: Gemini for everything except
pronunciation scoring, which is Azure). Swapping provider = re-implementing `AIClient`.
"""

import asyncio
import logging
from typing import Protocol, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}


class AIUnavailableError(RuntimeError):
    """All models in the chain failed (quota, overload, timeout or invalid output)."""


class AIClient(Protocol):
    async def generate_json(
        self, *, models: list[str], system: str, prompt: str, schema: type[T], temperature: float = 0.7
    ) -> tuple[T, str]: ...


class GeminiClient:
    def __init__(self, api_key: str, timeout: float = 120.0) -> None:
        self.raw = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
        self.timeout = timeout

    async def generate_json(
        self, *, models: list[str], system: str, prompt: str, schema: type[T], temperature: float = 0.7
    ) -> tuple[T, str]:
        """Return (parsed object, model id). Tries each model; one quick retry on transient errors."""
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
        )
        last: Exception | None = None
        for model in models:
            for attempt in range(2):
                try:
                    resp = await asyncio.wait_for(
                        self.raw.aio.models.generate_content(model=model, contents=prompt, config=config),
                        self.timeout,
                    )
                    parsed = (
                        resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate_json(resp.text or "")
                    )
                    return parsed, model
                except errors.APIError as e:
                    last = e
                    log.warning("Gemini %s failed (%s): %s", model, e.code, str(e)[:200])
                    if e.code not in RETRYABLE_CODES:
                        raise AIUnavailableError(f"Gemini từ chối yêu cầu ({e.code}).") from e
                    if e.code == 429:  # quota for this model: go straight to the next model
                        break
                except (TimeoutError, ValidationError, ValueError) as e:
                    last = e
                    log.warning("Gemini %s attempt %d failed: %s", model, attempt + 1, type(e).__name__)
                await asyncio.sleep(1.5 * (attempt + 1))
        raise AIUnavailableError("Gemini đang quá tải hoặc hết quota, vui lòng thử lại sau.") from last


_client: AIClient | None = None


def get_ai() -> AIClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = GeminiClient(s.gemini_api_key, s.ai_timeout_seconds)
    return _client


def set_ai(client: AIClient | None) -> None:
    """Override the AI client (tests)."""
    global _client
    _client = client


def get_genai_client() -> genai.Client:
    """Raw google-genai client for the Live API (conversation)."""
    ai = get_ai()
    if isinstance(ai, GeminiClient):
        return ai.raw
    s = get_settings()
    return genai.Client(api_key=s.gemini_api_key, http_options={"api_version": "v1beta"})
