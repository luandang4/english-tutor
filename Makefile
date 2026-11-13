# English Tutor — common tasks. Run `make help`.
.PHONY: help setup tts-model dev dev-backend dev-frontend build start test lint format migration smoke provision bootstrap deploy

help:
	@echo "setup         install backend (uv) + frontend (npm) dependencies + TTS model"
	@echo "tts-model     download the Kokoro TTS model (~340 MB) into data/models/"
	@echo "dev           run backend :8000 + Vite dev server :5173 (hot reload) — open http://localhost:5173"
	@echo "build         build the frontend into frontend/dist"
	@echo "start         build + serve everything from FastAPI — open http://127.0.0.1:8000"
	@echo "test          backend tests (fake Gemini, no quota) + frontend typecheck/lint"
	@echo "lint/format   ruff + oxlint"
	@echo "migration     new Alembic migration after changing models: make migration m='message'"
	@echo "smoke         live Gemini conversation smoke test: SMOKE_EMAIL=.. SMOKE_PASSWORD=.. make smoke"
	@echo "provision     AWS: S3 bucket, IAM role, security group, EC2, Elastic IP (once)"
	@echo "bootstrap     first-time server setup + .env + first deploy (once, after provision)"
	@echo "deploy        deploy pushed origin/main to EC2"

setup:
	cd backend && uv sync
	cd frontend && npm install
	$(MAKE) tts-model

tts-model:
	cd backend && uv run python scripts/download_tts_model.py

dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

start: build
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

test:
	cd backend && uv run pytest -q
	cd frontend && npm run typecheck && npm run lint

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

format:
	cd backend && uv run ruff check . --fix && uv run ruff format .

migration:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

smoke:
	cd backend && uv run python scripts/smoke_live.py

provision:
	deploy/provision.sh

bootstrap:
	deploy/bootstrap.sh

deploy:
	deploy/deploy.sh
