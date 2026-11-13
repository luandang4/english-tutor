from app.services.speech.tts import _chain


def test_words_and_sentences_use_different_sources() -> None:
    assert _chain("itinerary") == ["google", "dictionary", "kokoro"]
    assert _chain("boarding pass") == ["google", "dictionary", "kokoro"]
    assert _chain("Let the soup simmer for twenty minutes.") == ["kokoro", "google"]


async def test_fallback_audio_is_upgraded_when_preferred_source_recovers(tmp_path, monkeypatch) -> None:
    import os
    import time

    from app.services.speech import tts

    monkeypatch.setattr(tts, "CACHE_DIR", tmp_path)
    calls = {"google": 0}

    async def google(text):  # noqa: ANN001, ANN202
        calls["google"] += 1
        if calls["google"] == 1:
            raise RuntimeError("rate limited")
        return b"G", ".mp3"

    async def dictionary(text):  # noqa: ANN001, ANN202
        return b"D", ".mp3"

    monkeypatch.setitem(tts.SOURCES, "google", google)
    monkeypatch.setitem(tts.SOURCES, "dictionary", dictionary)

    assert (await tts.synthesize("season"))[2] == "dictionary"  # google down -> fallback
    assert (await tts.synthesize("season"))[2] == "dictionary"  # fresh fallback served from cache
    old = time.time() - tts.FALLBACK_RETRY_SECONDS - 1
    for f in tmp_path.iterdir():
        os.utime(f, (old, old))
    assert await tts.synthesize("season") == (b"G", "audio/mpeg", "google")  # upgraded
    assert [f.name.split(".")[1] for f in tmp_path.iterdir()] == ["google"]
