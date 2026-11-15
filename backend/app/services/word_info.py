"""Words the learner adds by hand (plan C7): dictionary data (meaning, IPA, example) from one Gemini call.

`fill_word` alone does not check access; `add_user_word` does (Feature.VOCABULARY quota) before calling Gemini.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import Feature
from app.models.user import User
from app.models.vocab import VocabCard
from app.schemas.ai import WordInfo
from app.services import access, srs
from app.services.ai.client import get_ai
from app.services.ai.prompts import TEACHER_SYSTEM, word_info_prompt


def needs_ai(data: dict[str, Any]) -> bool:
    return not str(data.get("meaning_vi", "")).strip()


async def fill_word(word: str, context: str = "") -> dict[str, Any]:
    """Word data (word + srs.WORD_FIELDS) from Gemini. Raises AIUnavailableError."""
    info, _ = await get_ai().generate_json(
        models=get_settings().content_models,
        system=TEACHER_SYSTEM,
        prompt=word_info_prompt(word, context),
        schema=WordInfo,
        temperature=0.3,
    )
    data = info.model_dump()
    data["word"] = " ".join(data["word"].split()) or word
    return data


async def add_user_word(
    session: AsyncSession, user: User, data: dict[str, Any], context: str = "", source: str = "manual"
) -> tuple[VocabCard, bool]:
    """Add a word typed by the learner. An existing word is returned without spending quota; missing meaning
    data is filled by Gemini (counts as one Từ vựng request). Commits."""
    existing = await srs.find_card(session, user.id, data["word"])
    if existing is not None:
        return existing, False
    if needs_ai(data):
        await access.ensure_quota(session, user, Feature.VOCABULARY)
        filled = await fill_word(data["word"], context)
        data = {**filled, **{k: v for k, v in data.items() if v and k != "word"}}
        await access.record_usage(session, user.id, Feature.VOCABULARY)
    card, created = await srs.add_word(session, user.id, data, source=source)
    await session.commit()
    return card, created
