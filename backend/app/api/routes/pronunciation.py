"""Pronunciation scoring (Azure) for a recorded word / sentence."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import CurrentUser, SessionDep, get_owned, require_feature
from app.core.constants import Feature
from app.models.pronunciation import PronunciationAttempt
from app.models.vocab import VocabCard
from app.schemas.api import PhonemeOut, PronunciationOut, WordScoreOut
from app.services import access
from app.services.speech import azure

router = APIRouter(
    prefix="/pronunciation", tags=["pronunciation"], dependencies=[require_feature(Feature.PRONUNCIATION)]
)
MAX_BYTES = azure.SAMPLE_RATE * 2 * azure.MAX_SECONDS


@router.post("/assess", response_model=PronunciationOut)
async def assess(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    reference_text: str = Query(min_length=1, max_length=300),
    card_id: int | None = None,
) -> PronunciationOut:
    """Body: raw PCM16 mono 16 kHz (application/octet-stream)."""
    if card_id is not None:
        await get_owned(session, VocabCard, card_id, user, "Thẻ từ")
    pcm = await request.body()
    if len(pcm) > MAX_BYTES:
        raise HTTPException(413, f"Ghi âm tối đa {azure.MAX_SECONDS} giây.")
    await access.ensure_quota(session, user, Feature.PRONUNCIATION)
    try:
        result = await azure.assess(pcm, reference_text)
    except azure.PronunciationError as e:
        raise HTTPException(422, str(e)) from e
    await access.record_usage(session, user.id, Feature.PRONUNCIATION)

    words = [
        WordScoreOut(
            word=w.word, score=w.score, error_type=w.error_type, phonemes=[PhonemeOut(**p) for p in w.phonemes]
        )
        for w in result.words
    ]
    row = PronunciationAttempt(
        user_id=user.id,
        card_id=card_id,
        reference_text=reference_text,
        recognized_text=result.recognized_text,
        pron_score=result.pron_score,
        accuracy=result.accuracy,
        fluency=result.fluency,
        completeness=result.completeness,
        prosody=result.prosody,
        words=[w.model_dump() for w in words],
    )
    session.add(row)
    await session.commit()
    return PronunciationOut(
        id=row.id,
        reference_text=reference_text,
        recognized_text=result.recognized_text,
        pron_score=result.pron_score,
        accuracy=result.accuracy,
        fluency=result.fluency,
        completeness=result.completeness,
        prosody=result.prosody,
        words=words,
    )
