"""Pronunciation assessment entry point: picks the engine (PRONUNCIATION_ENGINE).

- azure: Azure Pronunciation Assessment (accurate, paid after the free monthly hours)
- local: on-server phoneme model (free, an estimate) — services/speech/phoneme.py
- auto:  Azure first; when Azure itself is unavailable (quota, key, network) fall back to the local model
"""

import logging

from app.core.config import get_settings
from app.services.speech import azure, phoneme
from app.services.speech.azure import Assessment, PronunciationError

log = logging.getLogger(__name__)
MIN_SECONDS = 0.3


def available() -> bool:
    engine = get_settings().pronunciation_engine
    azure_ok = get_settings().azure_enabled
    if engine == "azure":
        return azure_ok
    if engine == "local":
        return phoneme.available()
    return azure_ok or phoneme.available()


def _check_length(pcm16: bytes) -> None:
    if len(pcm16) < azure.SAMPLE_RATE * 2 * MIN_SECONDS:
        raise PronunciationError("Đoạn ghi âm quá ngắn.")
    if len(pcm16) > azure.SAMPLE_RATE * 2 * azure.MAX_SECONDS:
        raise PronunciationError(f"Đoạn ghi âm dài quá {azure.MAX_SECONDS} giây.")


async def assess(pcm16: bytes, reference_text: str) -> Assessment:
    _check_length(pcm16)
    engine = get_settings().pronunciation_engine
    if engine == "local":
        return await phoneme.assess(pcm16, reference_text)
    if engine == "azure" or not phoneme.available():
        return await azure.assess(pcm16, reference_text)
    try:
        return await azure.assess(pcm16, reference_text)
    except PronunciationError as e:
        if not e.service_issue:
            raise
        log.warning("Azure unavailable (%s): using the local phoneme model", e)
        return await phoneme.assess(pcm16, reference_text)
