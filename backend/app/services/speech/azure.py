"""Azure Pronunciation Assessment (REST, short audio) — the ONLY Azure usage in the app.

Docs: https://learn.microsoft.com/azure/ai-services/speech-service/how-to-pronunciation-assessment
"""

import base64
import json
import struct
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings

SAMPLE_RATE = 16_000
MAX_SECONDS = 30


class PronunciationError(RuntimeError):
    def __init__(self, message: str, service_issue: bool = False) -> None:
        super().__init__(message)
        self.service_issue = service_issue  # Azure itself unavailable (quota, key, network): a fallback may help


@dataclass
class WordScore:
    word: str
    score: float
    error_type: str
    phonemes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Assessment:
    recognized_text: str
    pron_score: float
    accuracy: float
    fluency: float | None
    completeness: float
    prosody: float | None
    words: list[WordScore]
    engine: str = "azure"  # "azure" | "local" (estimate)


def pcm16_to_wav(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(pcm))
    return header + pcm


def _num(d: dict[str, Any], key: str) -> float | None:
    v = d.get(key, d.get("PronunciationAssessment", {}).get(key))
    return float(v) if v is not None else None


def parse_response(data: dict[str, Any]) -> Assessment:
    if data.get("RecognitionStatus") != "Success" or not data.get("NBest"):
        raise PronunciationError("Không nhận được giọng nói. Hãy nói rõ hơn và gần micro hơn.")
    best = data["NBest"][0]
    words = []
    for w in best.get("Words", []):
        pa = w.get("PronunciationAssessment", w)
        words.append(
            WordScore(
                word=w.get("Word", ""),
                score=float(pa.get("AccuracyScore", 0)),
                error_type=pa.get("ErrorType", "None"),
                phonemes=[
                    {"phoneme": p.get("Phoneme", ""), "score": float(_num(p, "AccuracyScore") or 0)}
                    for p in w.get("Phonemes", [])
                ],
            )
        )
    return Assessment(
        recognized_text=best.get("Display", data.get("DisplayText", "")),
        pron_score=_num(best, "PronScore") or 0.0,
        accuracy=_num(best, "AccuracyScore") or 0.0,
        fluency=_num(best, "FluencyScore") or 0.0,
        completeness=_num(best, "CompletenessScore") or 0.0,
        prosody=_num(best, "ProsodyScore"),
        words=words,
    )


async def assess(pcm16: bytes, reference_text: str) -> Assessment:
    s = get_settings()
    if not s.azure_enabled:
        raise PronunciationError("Chưa cấu hình Azure Speech (AZURE_SPEECH_KEY).", service_issue=True)
    if len(pcm16) < SAMPLE_RATE * 2 * 0.3:
        raise PronunciationError("Đoạn ghi âm quá ngắn.")
    if len(pcm16) > SAMPLE_RATE * 2 * MAX_SECONDS:
        raise PronunciationError(f"Đoạn ghi âm dài quá {MAX_SECONDS} giây.")

    params = {
        "ReferenceText": reference_text,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableMiscue": True,
        "EnableProsodyAssessment": True,
    }
    url = (
        f"https://{s.azure_speech_region}.stt.speech.microsoft.com/speech/recognition/conversation/"
        "cognitiveservices/v1?language=en-US&format=detailed"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": s.azure_speech_key,
        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        "Accept": "application/json",
        "Pronunciation-Assessment": base64.b64encode(json.dumps(params).encode()).decode(),
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, content=pcm16_to_wav(pcm16))
    except httpx.HTTPError as e:
        raise PronunciationError("Không kết nối được Azure Speech.", service_issue=True) from e
    if resp.status_code == 401:
        raise PronunciationError("Azure Speech key không hợp lệ.", service_issue=True)
    if resp.status_code in (403, 429):
        raise PronunciationError(
            "Azure Speech đã hết quota hoặc đang giới hạn tốc độ, thử lại sau.", service_issue=True
        )
    if resp.status_code >= 400:
        raise PronunciationError(f"Azure Speech lỗi {resp.status_code}.", service_issue=True)
    return parse_response(resp.json())
