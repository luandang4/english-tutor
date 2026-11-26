"""Pronunciation audio for words / example sentences (free sources, cached) — see services/speech/tts.py."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import CurrentUser, require_any_feature
from app.services.speech.tts import TTSError, synthesize

router = APIRouter(prefix="/tts", tags=["tts"], dependencies=[Depends(require_any_feature)])


async def word_audio(text: str, source: str | None, cache: str = "private") -> Response:
    """Audio response for `text` (also used by quiz listening questions, which address the word by id)."""
    try:
        audio, media_type, used = await synthesize(text.strip(), None if source in (None, "auto") else source)
    except TTSError as e:
        raise HTTPException(503, str(e)) from e
    return Response(
        audio,
        media_type=media_type,
        headers={"Cache-Control": f"{cache}, max-age=86400", "X-TTS-Source": used},
    )


@router.get("", response_class=Response)
async def tts(
    _: CurrentUser,
    text: str = Query(min_length=1, max_length=300),
    source: str | None = Query(None, pattern="^(auto|google|kokoro)$"),
) -> Response:
    return await word_audio(text, source, cache="public")
