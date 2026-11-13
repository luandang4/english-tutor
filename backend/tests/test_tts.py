from app.services.speech.tts import _chain


def test_words_and_sentences_use_different_sources() -> None:
    assert _chain("itinerary") == ["google", "dictionary", "kokoro"]
    assert _chain("boarding pass") == ["google", "dictionary", "kokoro"]
    assert _chain("Let the soup simmer for twenty minutes.") == ["kokoro", "google"]


async def test_fallback_audio_is_upgraded_when_preferred_source_recovers(tmp_path, monkeypatch) -> None:
    import os
    import time

    from app.services.speech import tts
    from app.services.speech.audio_store import LocalAudioStore

    monkeypatch.setattr(tts, "get_store", lambda: LocalAudioStore(tmp_path))
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


def test_chosen_source_goes_first_with_default_chain_as_fallback() -> None:
    assert _chain("season", "kokoro") == ["kokoro", "google", "dictionary"]
    assert _chain("season", "dictionary") == ["dictionary", "google", "kokoro"]
    assert _chain("Let the soup simmer.", "google") == ["google", "kokoro"]
    assert _chain("season", None) == ["google", "dictionary", "kokoro"]


async def test_cache_cleanup_removes_old_files_then_oldest_over_size(tmp_path) -> None:
    import os

    from app.services.speech.audio_store import LocalAudioStore, cleanup

    store = LocalAudioStore(tmp_path)
    now = 1_000_000_000.0
    day = 86400

    def make(name: str, age_days: float, size: int) -> None:
        f = tmp_path / name
        f.write_bytes(b"x" * size)
        os.utime(f, (now - age_days * day, now - age_days * day))

    make("expired.mp3", 31, 10)
    make("oldest.mp3", 20, 100)
    make("middle.mp3", 10, 100)
    make("newest.mp3", 1, 100)

    removed = await cleanup(store, max_age_days=30, max_bytes=250, now=now)
    assert removed == 2  # expired by age, then oldest dropped to fit 250 bytes
    assert sorted(f.name for f in tmp_path.iterdir()) == ["middle.mp3", "newest.mp3"]
    assert await cleanup(store, 30, 250, now=now) == 0


class FakeS3:
    """Just enough of the boto3 S3 client for S3AudioStore."""

    def __init__(self) -> None:
        from datetime import UTC, datetime

        self.now = lambda: datetime.now(UTC)
        self.objects: dict[str, tuple[bytes, object]] = {}

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):  # noqa: ANN001, ANN201, N803
        items = [
            {"Key": k, "Size": len(v[0]), "LastModified": v[1]} for k, v in self.objects.items() if k.startswith(Prefix)
        ]
        return {"Contents": items, "IsTruncated": False}

    def get_object(self, Bucket, Key):  # noqa: ANN001, ANN201, N803
        import io

        return {"Body": io.BytesIO(self.objects[Key][0])}

    def put_object(self, Bucket, Key, Body):  # noqa: ANN001, ANN201, N803
        self.objects[Key] = (Body, self.now())

    def delete_object(self, Bucket, Key):  # noqa: ANN001, ANN201, N803
        self.objects.pop(Key, None)

    def copy_object(self, Bucket, Key, CopySource, MetadataDirective):  # noqa: ANN001, ANN201, N803
        self.objects[Key] = (self.objects[CopySource["Key"]][0], self.now())


async def test_s3_store_caches_audio(monkeypatch) -> None:
    from app.services.speech import tts
    from app.services.speech.audio_store import S3AudioStore

    s3 = FakeS3()
    monkeypatch.setattr(tts, "get_store", lambda: S3AudioStore("bucket", "tts/", client=s3))
    calls = []

    async def google(text):  # noqa: ANN001, ANN202
        calls.append(text)
        return b"G", ".mp3"

    monkeypatch.setitem(tts.SOURCES, "google", google)
    assert await tts.synthesize("harbour") == (b"G", "audio/mpeg", "google")
    assert await tts.synthesize("harbour") == (b"G", "audio/mpeg", "google")
    assert calls == ["harbour"]  # second call served from S3
    [key] = s3.objects
    assert key.startswith("tts/") and key.endswith(".google.mp3")
