# English Tutor

A personal AI English tutor for Vietnamese learners: voice conversation with tutor "Emma", vocabulary,
grammar, essay writing, spaced-repetition review and pronunciation scoring. Each learner has their own
account and progress.

## Tech

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async) + Alembic, SQLite
- **Frontend:** React 19, TypeScript, Vite, TanStack Query
- **AI:** Gemini (lessons, grading, live voice conversation); Azure Speech only for pronunciation scoring;
  Kokoro-82M (local, open source) for example-sentence audio

Details of the stack, architecture and folder structure: [docs/TECHSTACK.md](docs/TECHSTACK.md).
How the main parts work (Vietnamese, for developers): [docs/TECHNICAL_OVERVIEW.md](docs/TECHNICAL_OVERVIEW.md).

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed automatically)
- Node.js 20+
- A `.env` file at the project root, created from `.env.example`:
  - `GEMINI_API_KEY` (required)
  - `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` (optional; without them pronunciation scoring is off)

## Run

```bash
make setup     # install dependencies + download the TTS model (~340 MB, first time only)
make start     # build the frontend and serve everything at http://127.0.0.1:8000
```

For development with hot reload:

```bash
make dev       # backend :8000 + Vite :5173 → open http://localhost:5173
```

The database (`data/app.db`) is created and migrated on startup. The first account you register becomes
**admin**; later accounts wait for an admin to approve them in `/admin`.

## Tests

```bash
make test      # pytest (fake Gemini, no quota) + TypeScript typecheck + lint
make smoke     # real Gemini Live conversation test (server must be running; uses quota)
```

## Notes

- The microphone only works on `localhost` or over HTTPS.
- On Gemini's free tier, Google may use your data to improve its products. Don't put sensitive
  information in conversations.
- Production: https://english-tutor.us.ci (AWS EC2). Deployment steps are in
  [docs/TECHSTACK.md](docs/TECHSTACK.md).
