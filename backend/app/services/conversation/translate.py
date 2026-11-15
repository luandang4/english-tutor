"""On-demand translation of Emma's sentences and word lookups (regular Gemini, not Live).

Cheap and frequent, so it is not counted against the daily quota; instead identical requests are served from
an in-memory cache and each user is rate-limited.
"""

import time
from collections import OrderedDict, deque

from app.core.config import get_settings
from app.schemas.ai import TextTranslation
from app.services.ai.client import get_ai

CACHE_SIZE = 1000
RATE_LIMIT = 30  # requests per user ...
RATE_WINDOW_S = 60.0  # ... per this many seconds

SYSTEM = (
    "You translate English for a Vietnamese learner of English. Answer with natural, concise Vietnamese. "
    "Never add explanations outside the requested fields."
)

CacheKey = tuple[str, str, str]
_cache: OrderedDict[CacheKey, TextTranslation] = OrderedDict()
_requests: dict[int, deque[float]] = {}


class RateLimitedError(RuntimeError):
    """The user sent too many translation requests in a short time."""


def _prompt(text: str, mode: str, context: str) -> str:
    if mode == "word":
        return (
            f"Word or phrase: {text}\nSentence it appears in: {context or text}\n"
            "Give its Vietnamese meaning in this sentence (a few words), its US IPA and part of speech."
        )
    return f"Translate this English into Vietnamese:\n{text}\nLeave `ipa` and `part_of_speech` empty."


def check_rate(user_id: int, now: float | None = None) -> None:
    """Sliding-window limit per user; raises RateLimitedError when exceeded."""
    now = time.monotonic() if now is None else now
    window = _requests.setdefault(user_id, deque())
    while window and now - window[0] > RATE_WINDOW_S:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        raise RateLimitedError("Bạn tra quá nhanh, hãy thử lại sau ít giây.")
    window.append(now)


def cache_key(text: str, mode: str, context: str) -> CacheKey:
    text = " ".join(text.split())
    if mode == "word":
        return (mode, text.lower(), " ".join(context.split()))
    return (mode, text, "")


def _cache_get(key: CacheKey) -> TextTranslation | None:
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    return None


def _cache_put(key: CacheKey, value: TextTranslation) -> None:
    _cache[key] = value
    if len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)


async def translate(text: str, mode: str, context: str = "") -> TextTranslation:
    """Vietnamese for one sentence (mode "sentence") or one word in its sentence (mode "word")."""
    key = cache_key(text, mode, context)
    if cached := _cache_get(key):
        return cached
    _, clean_text, clean_context = key
    result, _ = await get_ai().generate_json(
        models=get_settings().grading_models,
        system=SYSTEM,
        prompt=_prompt(" ".join(text.split()) if mode == "word" else clean_text, mode, clean_context),
        schema=TextTranslation,
        temperature=0.2,
    )
    _cache_put(key, result)
    return result
