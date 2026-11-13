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
| Styling | hand-written CSS design tokens (pastel purple primary, neon pink accent, cyan for the learner), dark/light via `prefers-color-scheme`. Components only use semantic tokens (`--primary`, `--accent`, `--cool`, …) |
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

## Custom topics

Vocabulary, grammar and writing hubs have a "Chủ đề của bạn" form: a topic title plus optional wishes.
`POST /api/lessons` / `POST /api/writing/tasks` accept either `topic_id` (preset) or `custom: {title, request}`
(lessons also need `skill`). The service creates a private `Topic` row (`user_id` = owner, `focus` = wishes);
the prompt treats the wishes as content guidance only (structure, counts and level stay fixed). Custom topics
are never listed in `/api/topics`, cannot be used by other users (404), and are deleted with the last lesson /
task that uses them (`services/topics.py`).

## Conversation tutor

- **Level-locked behaviour** (`services/conversation/tutor.py`): one shared rule set plus a small `LEVEL_POLICY`
  per CEFR level (English style, how much Vietnamese is allowed, correction style, enhancement on/off, reply
  length). The level chosen at the start is fixed for the session: the learner speaking Vietnamese never
  raises the amount of Vietnamese Emma uses.
- **Strict correction** on every level; **enhancement** (upgrading correct but plain sentences) only at B2/C1.
- **No cutting in**: Gemini Live VAD uses low end-of-speech sensitivity and `LIVE_END_OF_SPEECH_MS` (1200 ms)
  of silence before a learner turn ends.
- **Pronunciation from real audio only** (`services/conversation/pronunciation.py`): the server keeps each
  spoken learner turn's mic audio + transcript. After Emma has answered it, the turn is trimmed and scored by
  Azure (reference text = the transcript; mixed Vietnamese, typed, too short or >30 s turns are skipped). The
  result goes to the UI (score + weak words with a listen button, also saved in the transcript) and to the
  model as a `[Pronunciation data]` context message (`turn_complete=False`, held back while Emma is speaking
  because client content interrupts a Live answer). Without Azure the prompt forbids pronunciation claims.
  Disable with `LIVE_PRONUNCIATION=false`.

## Audio cache and options

- Generated word / sentence audio is cached (name = hash + source + extension) in `data/tts/` locally, or in S3
  in production (`TTS_STORAGE=s3`, `TTS_S3_BUCKET`, `TTS_S3_PREFIX`; `services/speech/audio_store.py`, EC2
  instance role, no keys). A background loop (hourly, and at startup) deletes files older than
  `TTS_CACHE_MAX_DAYS` (30) and then the oldest files until the cache is under `TTS_CACHE_MAX_MB` (1024); the S3
  bucket also has a 30-day lifecycle rule. Deleted audio is simply regenerated on demand.
- The learner picks the audio source per browser (lesson, review and account pages): Auto, Google
  Translate, human recording (Wiktionary), Kokoro. `GET /api/tts?source=...` puts the choice first and keeps the
  default chain as fallback.
- Conversation: "Đeo tai nghe" on = mic stays open while Emma speaks (barge-in); off = the client pauses the mic
  while she speaks.
- The tutor always uses the Gemini voice `Kore` (no voice picker).

## Admin, permissions & daily limits

Anything that spends AI quota is a **feature**: `conversation`, `vocabulary`, `grammar`, `writing`
(Gemini) and `pronunciation` (Azure). `services/access.py` decides access; a feature is usable when:

1. the account is active (locked accounts are signed out everywhere and cannot log in),
2. the feature is switched on system-wide (admin kill switch; applies to admins too),
3. the user was granted it (admins have every feature),
4. today's usage is under the daily limit (per user, admins exempt; conversation in minutes, the rest in
   AI requests; day boundary in `TIMEZONE`).

**Enforced by the API, not the UI.** Routers depend on `require_feature(...)`; actions that call an AI also
run `access.ensure_quota()` + `record_usage()` (`usage_events` table). The conversation WebSocket checks the
feature and caps the session at the minutes left today; live pronunciation scoring checks the pronunciation
feature and its limit per turn. `/api/tts` needs an approved account. Denials are `403` (not allowed /
switched off) or `429` (daily limit). The frontend hides or locks what `me.features` does not include
(`FeatureGate`, nav lock icons), but a hand-crafted request gets the same 403 / 429.

- System settings live in `app_settings` (key `system`): `features_enabled`, `daily_limits`,
  `registration_open`, `default_features` (granted to new sign-ups; empty = **wait for admin approval**).
- Web sign-up needs `ALLOW_REGISTRATION=true` in `.env` **and** the admin switch.
- The first account ever created becomes admin; `deploy/create-user.sh EMAIL "Name" [--admin]` adds accounts
  from the command line. Admins cannot lock or demote themselves (there is always one admin).
- Admin UI: `/admin` (system switches + limits, users with grants / lock / admin, today's usage).
- Learners see today's usage vs limits on the dashboard (`GET /api/auth/me/usage`).
- Passwords: at least 8 characters with a letter and a digit (`core/security.py: password_problem`, same rules
  shown live under the password field).

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

`users` + `auth_sessions` · `topics` (seeded presets with `user_id` NULL, plus learners' custom topics with `user_id` set) · per user: `lessons` (+ `exercise_attempts`) ·
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
      conversation/      Gemini Live config (live.py), tutor rules per CEFR level (tutor.py),
                   per-turn pronunciation evidence (pronunciation.py)
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

## Deployment (AWS EC2)

Everything is scripted in `deploy/` (AWS profile `new-frontiers`, region `ap-southeast-2`, see `deploy/config.sh`).

| Resource | Value |
| --- | --- |
| EC2 | `english-tutor`, t3.small, Ubuntu 24.04, 20 GB gp3 (encrypted), 2 GB swap |
| Domain | https://english-tutor.us.ci (A record → the instance's Elastic IP, tag `english-tutor`) |
| S3 | `english-tutor-tts-<account id>`, private (Block Public Access), `tts/` expires after 30 days |
| IAM | role / instance profile `english-tutor-ec2`: S3 access to that bucket only |
| Security group | `english-tutor-web`: 80/443 open, 22 only from the deploying machine's IP |
| SSH key | `~/.ssh/english-tutor.pem` (never committed; `ssh -i ~/.ssh/english-tutor.pem ubuntu@english-tutor.us.ci`) |

On the server: Caddy (HTTPS via Let's Encrypt, security headers, 1 MB body limit, `deploy/Caddyfile`) → uvicorn on 127.0.0.1:8000
(systemd unit `english-tutor`, `deploy/english-tutor.service`). Code in `/opt/english-tutor` (git clone of the
public repo), SQLite + Kokoro model in `/opt/english-tutor/data`, `.env` (mode 600) = local `.env` + production
overrides.

```sh
make provision                    # once: AWS resources (re-run to allow SSH from a new IP)
make bootstrap                    # once: packages, .env, first release
git push origin main && make deploy   # every release: git reset to origin/main, uv sync, npm build, restart
deploy/set-env.sh ALLOW_REGISTRATION=false   # change one server setting + restart
deploy/create-user.sh you@example.com "Name"  # add an account while web sign-up is closed
deploy/enable-https.sh tutor.example.com     # after DNS points at the Elastic IP
```

## Public repository hygiene

The GitHub repo is public, so it must never contain: `.env` / API keys, `*.pem` / SSH keys, the SQLite DB,
`data/`, AWS account IDs or access keys. `.gitignore` covers these; deploy scripts look the account ID up at
runtime (`aws sts get-caller-identity`) and the server gets AWS access from its instance role only.
Knowing the code does not grant access: sign-up is closed, logins are rate limited, every API route needs a
session cookie, and SSH only accepts the deploy key from one IP.

## Production checklist

- [x] systemd + Caddy, S3 audio cache, SSH restricted
- [x] HTTPS (`deploy/enable-https.sh english-tutor.us.ci`): `COOKIE_SECURE=true`, `ALLOWED_ORIGINS` = the domain
- [x] `API_DOCS=false` (no `/docs`, `/openapi.json`)
- [x] web sign-up closed (`ALLOW_REGISTRATION=false`); accounts are added with `deploy/create-user.sh`
- [ ] backups of `/opt/english-tutor/data/app.db` (SQLite on the instance disk; none yet)
