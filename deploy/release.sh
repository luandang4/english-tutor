#!/usr/bin/env bash
# Runs ON the server: update code to origin/main, install deps, build frontend, restart.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd /opt/english-tutor
git fetch -q origin main
git reset -q --hard origin/main
echo "release $(git log -1 --format='%h %s')"

cd backend
uv sync -q --no-dev --frozen
[ -f ../data/models/kokoro-v1.0.onnx ] || uv run --no-dev python scripts/download_tts_model.py

cd ../frontend
# `npm ci` rejects the macOS-generated lock on Linux (npm omits some optional wasm deps), so install
# leniently from the lock without rewriting it.
npm install --no-audit --no-fund --no-save --loglevel=error
npm run -s build

sudo cp /opt/english-tutor/deploy/english-tutor.service /etc/systemd/system/english-tutor.service
if ! sudo cmp -s /opt/english-tutor/deploy/Caddyfile /etc/caddy/Caddyfile; then
  sudo cp /opt/english-tutor/deploy/Caddyfile /etc/caddy/Caddyfile
  sudo systemctl reload caddy
fi
sudo systemctl daemon-reload
sudo systemctl restart english-tutor
for _ in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1 && { echo "healthy"; exit 0; }
  sleep 2
done
echo "app did not become healthy" >&2
sudo journalctl -u english-tutor -n 40 --no-pager >&2
exit 1
