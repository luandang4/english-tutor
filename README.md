# English Tutor

A personal AI English tutor for Vietnamese learners.

| Feature | What it does | AI |
|---|---|---|
| 🎙️ **Conversation** | Talk to tutor "Emma" by voice in real-life scenarios or your own topic. Audio-reactive orb, live transcript, saved history | Gemini Live |
| 📖 **Vocabulary** | Pick a preset topic (or type your own topic + wishes) and the AI writes 10 new words (IPA, examples, collocations, audio) plus exercises. Words go into the review deck | Gemini + Kokoro |
| 🧩 **Grammar** | Pick a grammar point and get an explanation in Vietnamese, formulas, common mistakes Vietnamese learners make, and 10 graded exercises | Gemini |
| ✍️ **Writing** | Pick a task type and the AI writes the prompt, an outline and useful phrases. Each essay is graded on 4 criteria with highlighted corrections | Gemini |
| 🗂️ **Review** | Flashcards with FSRS spaced repetition | — |
| 🔊 **Pronunciation** | Record a word and get scores per word and per phoneme | **Azure Speech** |
| 📊 **Dashboard** | Streak, progress per skill, 4-week activity, recent work | — |
| 👤 **Accounts** | Sign up and log in. Each account has its own lessons, word deck, writing, conversations and progress | — |
| 🛡️ **Admin** | Grant features per user, switch features off system-wide, daily limits per user, approve new sign-ups | — |

Vendor rule: **Azure is used only for pronunciation scoring; Gemini handles everything else.** Word audio
is free: the Google Translate voice (gTTS), then real speaker recordings (Wiktionary). Example sentences
use **Kokoro-82M**, an open-source TTS model that runs locally. See
[docs/TECHSTACK.md](docs/TECHSTACK.md) for the stack, architecture and folder structure.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed automatically)
- Node.js 20+
- A `.env` file at the project root, created from `.env.example`:
  - `GEMINI_API_KEY` (required)
  - `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` (optional; without them the pronunciation button is hidden)

## Run

```bash
make setup     # install dependencies + download the TTS model (~340 MB, first time only)
make start     # build the frontend and serve everything at http://127.0.0.1:8000
```

For development with hot reload:

```bash
make dev       # backend :8000 + Vite :5173 → open http://localhost:5173
```

On startup the database (`data/app.db`, SQLite) is created and migrated automatically, and the preset
topics are seeded. Open the app, choose **Đăng ký** and create an account. The **first** account
automatically receives any data created before accounts existed. To stop anyone else signing up, set
`ALLOW_REGISTRATION=false` in `.env`.

**Production:** https://english-tutor.us.ci on AWS EC2, released with `make deploy` after pushing `main`.
Infrastructure, scripts and the HTTPS step are in `docs/TECHSTACK.md` → *Deployment*.

Every lesson has a **"Tạo bài tập mới"** button: Gemini writes a new exercise set on the same content
(round 2, 3, …) without repeating earlier questions.

## Tests

```bash
make test      # pytest (fake Gemini, no quota) + TypeScript typecheck + lint
make smoke     # real Gemini Live conversation test (server must be running; uses quota)
```

## Notes

- The microphone only works on `localhost` or over HTTPS.
- Without headphones, keep **"Tắt mic khi giáo viên nói"** on so Emma doesn't hear herself.
- Creating a lesson takes 10–60 s, depending on Gemini load (the free tier sometimes returns 503;
  the app automatically falls back to another model).
- On the free tier, Google may use your data to improve its products. Don't put sensitive
  information in conversations.
- After changing models: `make migration m="describe change"`.
