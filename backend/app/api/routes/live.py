"""WebSocket bridge: browser <-> Gemini Live voice session. Transcripts are saved to the DB.

Browser <-> /ws/conversation protocol
  client -> server
    text   {"type": "start", "level": "B1", "scenario": "free_talk", "enhancement": "low"|"medium"|"high"}
           (first message; custom scenario adds "custom_title", "custom_request")
    binary PCM16 mono 16 kHz mic audio
    text   {"type": "text", "text": "..."}   typed message
    text   {"type": "action", "action": "hint"|"auto_hint"|"check_in"|"translate"|"repeat"|"slower"}
           quick-help button / silence timer; mapped to a fixed instruction (services/conversation/actions.py)
    text   {"type": "stop"}
  server -> client
    text   {"type": "ready", "session_id": int}
           {"type": "limits", "seconds_left": int}   (right after ready: time left in this session)
           {"type": "wrap_up", "seconds_left": int}  (2 minutes left: Emma was told to wrap up)
           {"type": "session_end", "reason": "time_limit"}  (session limit reached; the socket closes next)
    text   {"type": "transcript", "role": "user"|"tutor", "text": "..."}
           {"type": "interrupted"} | {"type": "turn_complete"} | {"type": "error", "message": "..."}
    text   {"type": "pronunciation", "text", "score", "accuracy", "fluency", "prosody", "weak_words": [...]}
           (Azure result for the learner's previous spoken turn; arrives shortly after the turn)
    text   on-screen cards from Emma's function calls (services/conversation/tools.py):
           {"type": "translation", "english", "vietnamese"}
           {"type": "feedback", "kind": "correction"|"upgrade", "original", "better", "explain_vi"}
           {"type": "hint", "question_en", "question_vi", "frames": [...], "keywords": [{"en", "vi"}]}
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
from app.services.conversation import memory
from app.services.conversation.actions import MIN_ACTION_GAP_S, WRAP_UP_INSTRUCTION, action_instruction, wrap_up_delay
from app.services.conversation.live import INPUT_RATE, OPENING_PROMPT, VOICE, LiveSettings, live_config
from app.services.conversation.pronunciation import PronunciationCoach, TurnPronunciation
from app.services.conversation.tools import parse_tool_call
from app.services.conversation.transcript import Transcript

__all__ = ["Transcript", "router"]

log = logging.getLogger(__name__)
router = APIRouter()
_slots = asyncio.Semaphore(get_settings().max_concurrent_live_sessions)


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
    """Conversation must be allowed with minutes left today and this month. The session is capped at the
    smallest of: the plan's minutes per session (or the server default), minutes left today / this month."""
    async with SessionLocal() as db:
        await access.ensure_quota(db, user, Feature.CONVERSATION)
        left = await access.remaining_today(db, user, Feature.CONVERSATION)
        per_session = await access.max_session_minutes(db, user) or get_settings().max_live_session_minutes
        try:
            await access.ensure_feature(db, user, Feature.PRONUNCIATION)
            pronunciation = True
        except access.AccessError:
            pronunciation = False
    max_minutes = per_session if left is None else min(per_session, left)
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
        learner_context = await memory.tutor_context(db, user_id)
    log.info("conversation %s start %s", record_id, settings)

    # Browser input is buffered so it survives Gemini reconnects (Live connections get GoAway after ~10 min).
    inbox: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    reader = asyncio.create_task(_read_browser(ws, inbox, transcript))
    coach = _pronunciation_coach(ws, inbox, transcript, user, limits.pronunciation)
    resume: dict[str, str | None] = {"handle": None}
    first = True
    wrap_up: asyncio.Task | None = None
    try:
        async with asyncio.timeout(limits.max_seconds):
            while True:
                async with client.aio.live.connect(
                    model=s.live_model, config=live_config(settings, resume["handle"], coach.enabled, learner_context)
                ) as session:
                    if first:
                        first = False
                        await ws.send_json({"type": "ready", "session_id": record_id})
                        elapsed = time.monotonic() - started
                        left = max(0, int(limits.max_seconds - elapsed))
                        await ws.send_json({"type": "limits", "seconds_left": left})
                        wrap_up = _schedule_wrap_up(ws, inbox, limits.max_seconds, elapsed)
                        await session.send_client_content(
                            turns=types.Content(role="user", parts=[types.Part(text=OPENING_PROMPT)]),
                            turn_complete=True,
                        )
                    else:
                        log.info("conversation %s resumed Live session", record_id)
                    forward = asyncio.create_task(_forward(inbox, session, coach))
                    relay = asyncio.create_task(_relay(ws, session, resume, transcript, coach, settings.level))
                    done, pending = await asyncio.wait({forward, relay}, return_when=asyncio.FIRST_COMPLETED)
                    for t in pending:
                        t.cancel()
                    for t in done:
                        if exc := t.exception():
                            raise exc
                    if relay in done and relay.result() == "go_away" and resume["handle"]:
                        continue  # reconnect transparently with the resumption handle
                    break  # learner stopped / disconnected
    except TimeoutError:  # not an error for the learner: the UI shows a friendly end screen
        await _safe_send(ws, {"type": "session_end", "reason": "time_limit"})
    except WebSocketDisconnect:
        pass
    except Exception as e:  # surface provider errors (quota, 503, ...) to the UI
        log.exception("conversation %s error", record_id)
        await _safe_send(ws, {"type": "error", "message": f"{type(e).__name__}: {e}"[:500]})
    finally:
        reader.cancel()
        if wrap_up:
            wrap_up.cancel()
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


def _schedule_wrap_up(ws: WebSocket, inbox: asyncio.Queue, max_seconds: int, elapsed: float) -> asyncio.Task | None:
    """2 minutes before the session limit: tell Emma to wrap up and tell the UI."""
    delay = wrap_up_delay(max_seconds)
    if delay is None:
        return None

    async def wrap_up() -> None:
        await asyncio.sleep(max(0.0, delay - elapsed))
        await inbox.put(("text", WRAP_UP_INSTRUCTION))
        await _safe_send(ws, {"type": "wrap_up", "seconds_left": max_seconds - int(delay)})

    return asyncio.create_task(wrap_up())


async def _read_browser(ws: WebSocket, inbox: asyncio.Queue, transcript: Transcript) -> None:
    last_action = -MIN_ACTION_GAP_S
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
                if data.get("type") == "action":
                    instruction = action_instruction(data.get("action"))
                    now = time.monotonic()
                    if instruction and now - last_action >= MIN_ACTION_GAP_S:
                        last_action = now
                        await inbox.put(("text", instruction))
                    continue
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


async def _relay(
    ws: WebSocket, session: Any, resume: dict, transcript: Transcript, coach: PronunciationCoach, level: str
) -> str:
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
            if m.tool_call:
                await _answer_tool_calls(ws, session, transcript, m.tool_call, level)
            upd = m.session_resumption_update
            if upd and upd.resumable and upd.new_handle:
                resume["handle"] = upd.new_handle
            if m.go_away:
                log.info("GoAway received (time left %s)", m.go_away.time_left)
                return "go_away"


async def _answer_tool_calls(ws: WebSocket, session: Any, transcript: Transcript, tool_call: Any, level: str) -> None:
    """Show Emma's on-screen cards (translation / feedback / hint) in the UI, then let the model continue."""
    responses = []
    for call in tool_call.function_calls or []:
        if card := parse_tool_call(call, level):
            transcript.add_card(card)
            await ws.send_json(card.to_message())
        responses.append(
            types.FunctionResponse(id=call.id, name=call.name, response={"result": "shown" if card else "invalid"})
        )
    if responses:
        await session.send_tool_response(function_responses=responses)


async def _safe_send(ws: WebSocket, payload: dict) -> None:
    try:
        await ws.send_json(payload)
    except Exception:
        pass
