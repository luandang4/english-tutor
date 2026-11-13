"""Fire-and-forget background jobs (AI generation / grading) that outlive the HTTP request.

In-process is enough for a single-user app; swap for a real queue (arq, Celery) if it grows.
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

log = logging.getLogger(__name__)
_running: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro, name=name)
    _running.add(task)

    def _done(t: asyncio.Task[Any]) -> None:
        _running.discard(t)
        if not t.cancelled() and t.exception():
            log.error("Background job %s crashed", name, exc_info=t.exception())

    task.add_done_callback(_done)
    return task


async def wait_all(grace_seconds: float = 30) -> None:
    """Wait for running jobs (graceful shutdown / tests)."""
    if _running:
        await asyncio.wait(list(_running), timeout=grace_seconds)
