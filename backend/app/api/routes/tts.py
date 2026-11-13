"""Pronunciation audio for words / example sentences (free sources, cached) — see services/speech/tts.py."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import CurrentUser, require_any_feature
from app.services.speech.tts import TTSError, synthesize

router = APIRouter(prefix="/tts", tags=["tts"], dependencies=[Depends(require_any_feature)])


@router.get("", response_class=Response)
async def tts(
    _: CurrentUser,
    text: str = Query(min_length=1, max_length=300),
    source: str | None = Query(None, pattern="^(auto|google|dictionary|kokoro)$"),
) -> Response:
    try:
        audio, media_type, source = await synthesize(text.strip(), None if source == "auto" else source)
    except TTSError as e:
        raise HTTPException(503, str(e)) from e
    return Response(
        audio,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400", "X-TTS-Source": source},
    )
