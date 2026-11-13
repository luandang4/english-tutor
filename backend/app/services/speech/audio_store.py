"""Where generated pronunciation audio is cached: the local `data/tts/` folder or an S3 bucket.

Both stores keep flat file names `{key}.{source}{ext}` and expose the same small API, so the TTS service
does not care where audio lives. Pick with `TTS_STORAGE=local|s3` (+ `TTS_S3_BUCKET`, `TTS_S3_PREFIX`).
On EC2 the S3 store authenticates with the instance role (no keys in `.env`).
"""

import asyncio
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.core.config import DATA_DIR, get_settings


@dataclass(frozen=True)
class StoredAudio:
    name: str  # "{key}.{source}{ext}"
    size: int
    mtime: float  # unix seconds (S3: LastModified)


class AudioStore(Protocol):
    async def find(self, key: str) -> list[StoredAudio]: ...
    async def read(self, name: str) -> bytes: ...
    async def write(self, name: str, data: bytes) -> None: ...
    async def delete(self, name: str) -> None: ...
    async def touch(self, name: str) -> None: ...
    async def list_all(self) -> list[StoredAudio]: ...


class LocalAudioStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _stat(self, path: Path) -> StoredAudio:
        st = path.stat()
        return StoredAudio(path.name, st.st_size, st.st_mtime)

    async def find(self, key: str) -> list[StoredAudio]:
        return [self._stat(p) for p in self.root.glob(f"{key}.*") if p.is_file()]

    async def read(self, name: str) -> bytes:
        return await asyncio.to_thread((self.root / name).read_bytes)

    async def write(self, name: str, data: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread((self.root / name).write_bytes, data)

    async def delete(self, name: str) -> None:
        (self.root / name).unlink(missing_ok=True)

    async def touch(self, name: str) -> None:
        (self.root / name).touch()

    async def list_all(self) -> list[StoredAudio]:
        if not self.root.exists():
            return []
        return [self._stat(p) for p in self.root.iterdir() if p.is_file()]


class S3AudioStore:
    def __init__(self, bucket: str, prefix: str = "tts/", client: Any = None) -> None:
        self.bucket = bucket
        self.prefix = prefix
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("s3")
        return self._client

    def _list(self, prefix: str) -> list[StoredAudio]:
        items, token = [], None
        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = self.client.list_objects_v2(**kwargs)
            for o in page.get("Contents", []):
                name = o["Key"][len(self.prefix) :]
                items.append(StoredAudio(name, o["Size"], o["LastModified"].timestamp()))
            if not page.get("IsTruncated"):
                return items
            token = page["NextContinuationToken"]

    async def find(self, key: str) -> list[StoredAudio]:
        return await asyncio.to_thread(self._list, f"{self.prefix}{key}.")

    async def read(self, name: str) -> bytes:
        def get() -> bytes:
            return self.client.get_object(Bucket=self.bucket, Key=self.prefix + name)["Body"].read()

        return await asyncio.to_thread(get)

    async def write(self, name: str, data: bytes) -> None:
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=self.prefix + name, Body=data)

    async def delete(self, name: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=self.prefix + name)

    async def touch(self, name: str) -> None:
        key = self.prefix + name
        await asyncio.to_thread(
            self.client.copy_object,
            Bucket=self.bucket,
            Key=key,
            CopySource={"Bucket": self.bucket, "Key": key},
            MetadataDirective="REPLACE",  # required to copy onto itself; refreshes LastModified
        )

    async def list_all(self) -> list[StoredAudio]:
        return await asyncio.to_thread(self._list, self.prefix)


@lru_cache
def get_store() -> AudioStore:
    s = get_settings()
    if s.tts_storage == "s3":
        if not s.tts_s3_bucket:
            raise RuntimeError("TTS_STORAGE=s3 needs TTS_S3_BUCKET")
        return S3AudioStore(s.tts_s3_bucket, s.tts_s3_prefix)
    return LocalAudioStore(DATA_DIR / "tts")


async def cleanup(store: AudioStore, max_age_days: int, max_bytes: int, now: float | None = None) -> int:
    """Delete audio older than `max_age_days`, then the oldest files until the store fits `max_bytes`."""
    now = time.time() if now is None else now
    removed, keep = 0, []
    for item in await store.list_all():
        if now - item.mtime > max_age_days * 86400:
            await store.delete(item.name)
            removed += 1
        else:
            keep.append(item)
    total = sum(i.size for i in keep)
    for item in sorted(keep, key=lambda i: i.mtime):  # oldest first
        if total <= max_bytes:
            break
        await store.delete(item.name)
        total -= item.size
        removed += 1
    return removed
