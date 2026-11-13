# Tech stack & architecture

## Vendor rule (agreed, do not change without discussion)

| Provider | Used for | Never used for |
|---|---|---|
| **Azure Speech** | Pronunciation Assessment only (phoneme / word / fluency / prosody scores) | content generation, grading, conversation |
| **Google Gemini** | everything else: live voice conversation, lesson and exercise generation (vocabulary, grammar, writing tasks), answer and essay grading | pronunciation scoring, word audio |
| **Free pronunciation audio** (no paid AI) | single words: the Google Translate voice (gTTS), falling back to real speaker recordings from Wiktionary and then Kokoro. Sentences: Kokoro-82M, local and offline | anything else |

New AI features default to Gemini. All non-speech Gemini calls go through
`backend/app/services/ai/client.py` (model fallback chain), and all Azure calls go through
`backend/app/services/speech/azure.py`. Switching provider only touches these two modules.

## Gemini models (configurable in `.env`)

| Task | Default chain (tried in order) | Why |
|---|---|---|
| Live conversation | `gemini-3.8-live` | native-audio speech-to-speech, transcripts, session resumption |
| Lesson / writing-task generation | `gemini-3.5-flash` → `gemini-3.8-flash` → `gemini-3.5-flash-lite` | ~6 s for a lesson, structured JSON output |
| Short-answer grading | `gemini-3.5-flash-lite` → `gemini-3.5-flash` | ~1–2 s per answer |
| Essay grading | `gemini-3.5-flash` → `gemini-3.8-flash` | quality rubric feedback |

Fallback triggers: 429 (quota) moves straight to the next model; 5xx, timeouts and invalid JSON get
one retry, then the next model.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, **FastAPI**, Pydantic v2, pydantic-settings |
| Database | **SQLAlchemy 2.0 (async)** + **Alembic** migrations. SQLite (WAL) by default; Postgres via `DATABASE_URL` |
| Spaced repetition | **FSRS** (`fsrs` / py-fsrs) |
| Pronunciation audio | `services/speech/tts.py`, a source chain configured by `TTS_WORD_SOURCES` / `TTS_SENTENCE_SOURCES`. Words: **gTTS** ([pndurette/gTTS](https://github.com/pndurette/gTTS), the Google Translate voice; unofficial endpoint, free; consistent dictionary-style reading) → **Wiktionary recordings** (human volunteer recordings, CC-licensed; intonation varies, e.g. a rising "season") → **Kokoro-82M** ([kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), local CPU; it mis-stresses isolated words, so it is the last resort for words). Sentences: Kokoro → gTTS. Results are cached in `data/tts/`, and a new vocabulary lesson's words are prefetched in the background. On Intel Macs onnxruntime is pinned below 1.24 (the last release with macOS x86_64 wheels). The browser's built-in voice is used if everything fails |
| Background jobs | in-process asyncio tasks (`services/tasks.py`). Jobs interrupted by a restart are marked failed on boot |
| Frontend | **React 19 + TypeScript (strict) + Vite**, React Router (lazy routes), TanStack Query |
| Styling | hand-written CSS design tokens (pastel sunny yellow primary, neon coral accent, cyan for the learner), dark/light via `prefers-color-scheme`. Components only use semantic tokens (`--primary`, `--accent`, `--cool`, …) |
| Audio | AudioWorklet → PCM16 16 kHz (mic); WebAudio playback 24 kHz; canvas orb visualizer |
| Tooling | uv, ruff, pytest (fake Gemini, no quota), oxlint, `tsc -b` |

## Architecture

```
Browser (React SPA)
 ├─ REST /api/*  ──────────────►  FastAPI routers ─► services ─► SQLAlchemy ─► SQLite/Postgres
 │                                     │
 │                                     ├─ services/ai/client.py ──► Gemini (generate / grade, JSON schema)
 │                                     ├─ services/speech/tts.py ─► Wiktionary recordings / gTTS / Kokoro (cached)
 │                                     └─ services/speech/azure.py ► Azure Pronunciation Assessment
 └─ WebSocket /ws/conversation ─► api/routes/live.py ───────────► Gemini Live (bidirectional audio)
                                   (transcript saved to DB at the end)
```

- **Lesson / task generation is asynchronous**: `POST` returns at once with `status=generating`, a
  background job fills the content, and the UI polls until `ready` or `failed` (failed jobs can be retried).
- **Grading is rule-first**: multiple choice and exact fill-in matches are graded instantly with no
  AI call. Only open answers and non-matching fill-ins go to Gemini.
- **Answers are hidden** from the API until an exercise has been attempted.
- **Exercise rounds**: `POST /api/lessons/{id}/exercises/regenerate` asks Gemini for a fresh set on the same
  words or grammar point. All earlier questions are passed in so nothing repeats. Ids are unique per round
  (`r2e1`…), and the lesson score is the score of the latest completed round.
- **Writing scores** are recomputed server-side as the mean of the four criteria. Corrections that
  can't be located in the learner's text are dropped, so highlighting always works.

## Accounts & data isolation

- Email and password accounts. Passwords are hashed with **Argon2id** (`argon2-cffi`).
- Login creates a random 256-bit token in an **HttpOnly, SameSite=Lax cookie** (`et_session`). Only its
  SHA-256 is stored, in `auth_sessions`, so a database leak doesn't expose live sessions. Sessions last
  `SESSION_DAYS` (30). Logging out deletes the session server-side, and changing the password signs out
  every other device.
- Every learning table has `user_id`. Routes use `CurrentUser` and `get_owned()`, which returns **404**
  (not 403) for another user's rows so nothing leaks. Writing submissions are owned through their task,
  exercise attempts through their lesson, and review logs through their card. The vocabulary deck is
  unique per `(user_id, word_key)`.
- The conversation WebSocket checks the same cookie (plus an Origin check) before opening a Gemini Live
  session.
- Public endpoints: `/api/health`, `/api/meta`, `/api/topics`, `/api/auth/*`. Everything else, including
  `/api/tts`, requires login.
- Brute-force guard: at most 10 failed logins per IP per 15 minutes (in-memory). Unknown emails take the
  same time as wrong passwords.
- **Migration of existing data**: rows created before accounts existed have `user_id = NULL`, and the
  first account to register claims them.
- Settings: `ALLOW_REGISTRATION` (turn it off after creating your accounts), `COOKIE_SECURE` (set true
  behind HTTPS), `SESSION_DAYS`.

## Data model

`users` + `auth_sessions` · `topics` (shared, seeded presets) · per user: `lessons` (+ `exercise_attempts`) ·
`vocab_cards` (FSRS state) + `review_logs` · `writing_tasks` (+ `writing_submissions`) ·
`conversation_sessions` (transcripts) · `pronunciation_attempts`.

## Project layout

```
backend/
  app/
    main.py              app factory, lifespan (migrations, seed, stale-job cleanup), SPA serving
    core/                settings, constants (levels, skills, statuses), logging
    db/                  declarative base, UTC datetime type, async engine/session
    models/              ORM tables
    schemas/ai.py        JSON schemas Gemini must fill
    schemas/api.py       request/response DTOs
    services/            business logic (lessons, grading, srs, writing, progress, tasks)
      ai/                Gemini client + prompts
      speech/            Azure pronunciation + word/sentence audio chain
      conversation/      Gemini Live persona/config
    api/routes/          thin HTTP/WebSocket layer
    seed/topics.py       preset topics (edit to add more)
  alembic/               migrations
  tests/                 pytest (fake AI), fixtures
  scripts/smoke_live.py  real Gemini Live smoke test
frontend/
  src/
    api/                 typed client, DTO types, TanStack Query hooks
    components/          layout shell, ui kit, exercises, pronunciation
    features/            dashboard, conversation, lessons (vocab+grammar), vocabulary review, writing
    lib/                 audio (live session, recorder, TTS), formatting, preferences
    orb/                 audio-reactive canvas orb
    styles/global.css    design tokens + components
  public/pcm-worklet.js  mic capture AudioWorklet
docs/TECHSTACK.md
```

## Before deploying to a VPS

Accounts are built in. Before exposing the app:

- add HTTPS: browsers require it for the microphone (Caddy is the simplest option), and set `COOKIE_SECURE=true`
- after creating the accounts you need, set `ALLOW_REGISTRATION=false`
- restrict `ALLOWED_ORIGINS`
- run under systemd or Docker
