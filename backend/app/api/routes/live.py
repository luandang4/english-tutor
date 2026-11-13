"""WebSocket bridge: browser <-> Gemini Live voice session. Transcripts are saved to the DB.

Browser <-> /ws/conversation protocol
  client -> server
    text   {"type": "start", "level": "B1", "scenario": "free_talk"}  (first message)
    binary PCM16 mono 16 kHz mic audio
    text   {"type": "text", "text": "..."}   typed message
    text   {"type": "stop"}
  server -> client
    text   {"type": "pronunciation", "text", "score", "accuracy", "fluency", "prosody", "weak_words": [...]}
           (Azure result for the learner's previous spoken turn; arrives shortly after the turn)
    text   {"type": "ready", "session_id": int} | {"type": "transcript", "role": "user"|"tutor", "text": "..."}
           {"type": "interrupted"} | {"type": "turn_complete"} | {"type": "error", "message": "..."}
    binary PCM16 mono 24 kHz tutor audio
"""

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.genai import types

from app.core.config import get_settings
from app.core.constants import Feature
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.conversation import ConversationSession
from app.models.user import User
from app.services import access, auth
from app.services.ai.client import get_genai_client
from app.services.conversation.live import INPUT_RATE, OPENING_PROMPT, VOICE, LiveSettings, live_config
from app.services.conversation.pronunciation import PronunciationCoach, TurnPronunciation

log = logging.getLogger(__name__)
router = APIRouter()
_slots = asyncio.Semaphore(get_settings().max_concurrent_live_sessions)


class Transcript:
    """Merges streamed transcript fragments into turns."""

    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []

    def add(self, role: str, text: str) -> None:
        if self.turns and self.turns[-1]["role"] == role and not self.turns[-1].get("closed"):
            self.turns[-1]["text"] += text
        else:
            self.turns.append({"role": role, "text": text})

    def close_turn(self) -> None:
        if self.turns:
            self.turns[-1]["closed"] = True

    def last_user_index(self) -> int:
        return next((i for i in range(len(self.turns) - 1, -1, -1) if self.turns[i]["role"] == "user"), -1)

    def attach_pronunciation(self, index: int, data: dict[str, Any]) -> None:
        if 0 <= index < len(self.turns):
            self.turns[index]["pronunciation"] = data

    def export(self) -> list[dict[str, Any]]:
        out = []
        for t in self.turns:
            if text := t["text"].strip():
                turn = {"role": t["role"], "text": text}
                if "pronunciation" in t:
                    turn["pronunciation"] = t["pronunciation"]
                out.append(turn)
        return out


def _origin_allowed(ws: WebSocket) -> bool:
    """Block cross-site WebSocket hijacking: only our own page (or the Vite dev server) may connect."""
    origin = ws.headers.get("origin")
    if not origin:
        return True  # non-browser clients (tests, CLI)
    if origin in get_settings().allowed_origins:
        return True
    return urlparse(origin).netloc == ws.headers.get("host")


@router.websocket("/ws/conversation")
async def conversation_ws(ws: WebSocket) -> None:
    if not _origin_allowed(ws):
        await ws.close(code=1008)
        return
    async with SessionLocal() as db:
        user = await auth.user_for_token(db, ws.cookies.get(get_settings().session_cookie))
    await ws.accept()
    if user is None:
        await _safe_send(ws, {"type": "error", "message": "Bạn cần đăng nhập."})
        await ws.close(code=1008)
        return
    try:
        limits = await _session_limits(user)
    except access.AccessError as e:
        await _safe_send(ws, {"type": "error", "message": str(e)})
        await ws.close(code=1008)
        return
    try:
        start = await ws.receive_json()
    except (WebSocketDisconnect, json.JSONDecodeError):
        return

    if _slots.locked():
        await _safe_send(ws, {"type": "error", "message": "Đang có quá nhiều phiên hội thoại, hãy đóng tab khác."})
        await ws.close()
        return

    async with _slots:
        await _run_session(ws, LiveSettings.from_dict(start), user, limits)


@dataclass
class SessionLimits:
    max_seconds: int
    pronunciation: bool  # user may use (Azure) pronunciation scoring


async def _session_limits(user: User) -> SessionLimits:
    """Conversation must be allowed with minutes left today; the session is capped at what is left."""
    s = get_settings()
    async with SessionLocal() as db:
        await access.ensure_quota(db, user, Feature.CONVERSATION)
        left = await access.remaining_today(db, user, Feature.CONVERSATION)
        try:
            await access.ensure_feature(db, user, Feature.PRONUNCIATION)
            pronunciation = True
        except access.AccessError:
            pronunciation = False
    max_minutes = s.max_live_session_minutes if left is None else min(s.max_live_session_minutes, left)
    return SessionLimits(max_seconds=max_minutes * 60, pronunciation=pronunciation)


async def _run_session(ws: WebSocket, settings: LiveSettings, user: User, limits: SessionLimits) -> None:
    user_id = user.id
    s = get_settings()
    client = get_genai_client()
    transcript = Transcript()
    started = time.monotonic()
    async with SessionLocal() as db:
        record = ConversationSession(
            user_id=user_id,
            level=settings.level,
            scenario=settings.scenario,
            topic=settings.custom_title,
            voice=VOICE,
        )
        db.add(record)
        await db.commit()
        record_id = record.id
    log.info("conversation %s start %s", record_id, settings)

    # Browser input is buffered so it survives Gemini reconnects (Live connections get GoAway after ~10 min).
    inbox: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    reader = asyncio.create_task(_read_browser(ws, inbox, transcript))
    coach = _pronunciation_coach(ws, inbox, transcript, user, limits.pronunciation)
    resume: dict[str, str | None] = {"handle": None}
    first = True
    try:
        async with asyncio.timeout(limits.max_seconds):
            while True:
                async with client.aio.live.connect(
                    model=s.live_model, config=live_config(settings, resume["handle"], coach.enabled)
                ) as session:
                    if first:
                        first = False
                        await ws.send_json({"type": "ready", "session_id": record_id})
                        await session.send_client_content(
                            turns=types.Content(role="user", parts=[types.Part(text=OPENING_PROMPT)]),
                            turn_complete=True,
                        )
                    else:
                        log.info("conversation %s resumed Live session", record_id)
                    forward = asyncio.create_task(_forward(inbox, session, coach))
                    relay = asyncio.create_task(_relay(ws, session, resume, transcript, coach))
                    done, pending = await asyncio.wait({forward, relay}, return_when=asyncio.FIRST_COMPLETED)
                    for t in pending:
                        t.cancel()
                    for t in done:
                        if exc := t.exception():
                            raise exc
                    if relay in done and relay.result() == "go_away" and resume["handle"]:
                        continue  # reconnect transparently with the resumption handle
                    break  # learner stopped / disconnected
    except TimeoutError:
        await _safe_send(ws, {"type": "error", "message": f"Buổi học đã đạt giới hạn {limits.max_seconds // 60} phút."})
    except WebSocketDisconnect:
        pass
    except Exception as e:  # surface provider errors (quota, 503, ...) to the UI
        log.exception("conversation %s error", record_id)
        await _safe_send(ws, {"type": "error", "message": f"{type(e).__name__}: {e}"[:500]})
    finally:
        reader.cancel()
        coach.close()
        duration = int(time.monotonic() - started)
        await _save(record_id, transcript, duration)
        async with SessionLocal() as db:  # Gemini Live is billed for the whole connection
            await access.record_usage(db, user_id, Feature.CONVERSATION, math.ceil(duration / 60))
        try:
            await ws.close()
        except Exception:  # noqa: BLE001 — the browser already disconnected
            pass


async def _save(record_id: int, transcript: Transcript, duration: int) -> None:
    turns = transcript.export()
    async with SessionLocal() as db:
        record = await db.get(ConversationSession, record_id)
        if record is None:
            return
        if not any(t["role"] == "user" for t in turns):
            await db.delete(record)  # learner never spoke: don't clutter history
        else:
            record.transcript = turns
            record.turns = sum(1 for t in turns if t["role"] == "user")
            record.duration_seconds = duration
            record.ended_at = utcnow()
        await db.commit()
    log.info("conversation %s end (%ss, %d turns)", record_id, duration, len(turns))


async def _read_browser(ws: WebSocket, inbox: asyncio.Queue, transcript: Transcript) -> None:
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes"):
                await inbox.put(("audio", msg["bytes"]))
            elif msg.get("text"):
                data = json.loads(msg["text"])
                if data.get("type") == "stop":
                    break
                text = str(data.get("text", "")).strip()[:1000]
                if data.get("type") == "text" and text:
                    transcript.close_turn()
                    transcript.add("user", text)
                    transcript.close_turn()
                    await inbox.put(("text", text))
    except (WebSocketDisconnect, RuntimeError, json.JSONDecodeError):
        pass
    finally:
        await inbox.put(("stop", None))


def _pronunciation_coach(
    ws: WebSocket, inbox: asyncio.Queue, transcript: Transcript, user: User, allowed: bool
) -> PronunciationCoach:
    """Scores each spoken learner turn (Azure); shows it in the UI, saves it, and tells the tutor model.
    Each scored turn counts against the user's daily pronunciation limit."""
    s = get_settings()

    async def allow() -> bool:
        async with SessionLocal() as db:
            left = await access.remaining_today(db, user, Feature.PRONUNCIATION)
        return left is None or left > 0

    async def on_result(turn_index: int, result: TurnPronunciation) -> None:
        async with SessionLocal() as db:
            await access.record_usage(db, user.id, Feature.PRONUNCIATION)
        data = result.to_dict()
        transcript.attach_pronunciation(turn_index, data)
        await _safe_send(ws, {"type": "pronunciation", **data})

    async def send_note(note: str) -> None:
        await inbox.put(("note", note))

    return PronunciationCoach(s.live_pronunciation and s.azure_enabled and allowed, on_result, send_note, allow)


async def _forward(inbox: asyncio.Queue, session: Any, coach: PronunciationCoach) -> None:
    mime = f"audio/pcm;rate={INPUT_RATE}"
    while True:
        kind, payload = await inbox.get()
        if kind == "stop":
            return
        if kind == "audio":
            coach.learner_audio(payload)
            await session.send_realtime_input(audio=types.Blob(data=payload, mime_type=mime))
        elif kind == "note":  # context only: must not trigger an answer
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=payload)]), turn_complete=False
            )
        else:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=payload)]), turn_complete=True
            )


async def _relay(ws: WebSocket, session: Any, resume: dict, transcript: Transcript, coach: PronunciationCoach) -> str:
    while True:  # session.receive() ends after each turn_complete
        async for m in session.receive():
            sc = m.server_content
            if m.data or (sc and sc.output_transcription and sc.output_transcription.text):
                coach.tutor_output()
            if m.data:
                await ws.send_bytes(m.data)
            if sc:
                if sc.input_transcription and sc.input_transcription.text:
                    coach.learner_text(sc.input_transcription.text)
                    transcript.add("user", sc.input_transcription.text)
                    await ws.send_json({"type": "transcript", "role": "user", "text": sc.input_transcription.text})
                if sc.output_transcription and sc.output_transcription.text:
                    transcript.add("tutor", sc.output_transcription.text)
                    await ws.send_json({"type": "transcript", "role": "tutor", "text": sc.output_transcription.text})
                if sc.interrupted:
                    transcript.close_turn()
                    await ws.send_json({"type": "interrupted"})
                    await coach.tutor_done(transcript.last_user_index())
                if sc.turn_complete:
                    transcript.close_turn()
                    await ws.send_json({"type": "turn_complete"})
                    await coach.tutor_done(transcript.last_user_index())
            upd = m.session_resumption_update
            if upd and upd.resumable and upd.new_handle:
                resume["handle"] = upd.new_handle
            if m.go_away:
                log.info("GoAway received (time left %s)", m.go_away.time_left)
                return "go_away"


async def _safe_send(ws: WebSocket, payload: dict) -> None:
    try:
        await ws.send_json(payload)
    except Exception:
        pass
