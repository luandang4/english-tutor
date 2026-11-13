"""End-to-end smoke test: browser protocol -> server -> Gemini Live, using a recorded learner clip.

Usage: SMOKE_EMAIL=you@example.com SMOKE_PASSWORD=... uv run python scripts/smoke_live.py [ws://127.0.0.1:8000/ws/conversation]
(the conversation endpoint requires a logged-in account)
"""

import asyncio
import json
import os
import sys
import time
import urllib.request
import wave
from pathlib import Path

import websockets

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8000/ws/conversation"


def login_cookie() -> str:
    http = URL.replace("ws://", "http://").replace("wss://", "https://").split("/ws/")[0]
    body = json.dumps({"email": os.environ["SMOKE_EMAIL"], "password": os.environ["SMOKE_PASSWORD"]}).encode()
    req = urllib.request.Request(f"{http}/api/auth/login", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.headers["Set-Cookie"].split(";")[0]


CLIP = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "learner_16k.wav"


async def read_turn(ws, label, t0):
    text, audio, first = {"user": "", "tutor": ""}, 0, None
    while True:
        msg = await asyncio.wait_for(ws.recv(), 60)
        if isinstance(msg, bytes):
            audio += len(msg)
            first = first or time.perf_counter() - t0
            continue
        m = json.loads(msg)
        if m["type"] == "transcript":
            text[m["role"]] += m["text"]
        elif m["type"] == "error":
            raise RuntimeError(m["message"])
        elif m["type"] == "turn_complete":
            print(f"[{label}] first audio {first:.2f}s, {audio / 48000:.1f}s audio")
            for r in ("user", "tutor"):
                if text[r].strip():
                    print(f"   {r}: {text[r].strip()}")
            assert audio > 0, "no tutor audio"
            return


async def main():
    async with websockets.connect(URL, max_size=None, additional_headers={"Cookie": login_cookie()}) as ws:
        t0 = time.perf_counter()
        await ws.send(json.dumps({"type": "start", "level": "A2", "scenario": "free_talk"}))
        assert json.loads(await ws.recv())["type"] == "ready"
        print(f"[ready] {time.perf_counter() - t0:.2f}s")
        await read_turn(ws, "greeting", t0)

        with wave.open(str(CLIP)) as w:
            pcm = w.readframes(w.getnframes())
        chunk = 3200  # 100 ms @16 kHz PCM16
        for i in range(0, len(pcm), chunk):  # stream in real time like a mic
            await ws.send(pcm[i : i + chunk])
            await asyncio.sleep(0.1)
        t1 = time.perf_counter()
        for _ in range(20):  # 2 s of silence so server VAD detects end of speech
            await ws.send(b"\x00" * chunk)
            await asyncio.sleep(0.1)
        await read_turn(ws, "voice reply (from end of speech)", t1)

        t2 = time.perf_counter()
        await ws.send(json.dumps({"type": "text", "text": "Can you say that more slowly?"}))
        await read_turn(ws, "text reply", t2)
        await ws.send(json.dumps({"type": "stop"}))
    print("SMOKE TEST PASSED")


asyncio.run(main())
