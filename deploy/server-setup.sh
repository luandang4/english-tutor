#!/usr/bin/env bash
# Runs ON the server (as ubuntu, via deploy/bootstrap.sh). Installs system packages once; safe to re-run.
set -euo pipefail
APP_DIR=/opt/english-tutor
REPO=https://github.com/luandang4/english-tutor.git

# swap: the 2 GB instance needs headroom for Kokoro + the frontend build
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq git curl ca-certificates gnupg debian-keyring \
  debian-archive-keyring apt-transport-https unattended-upgrades

# Node 22 (frontend build)
if ! command -v node >/dev/null || ! node --version | grep -q '^v22'; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -yq nodejs
fi
# same npm major as development, so `npm ci` accepts package-lock.json
npm --version | grep -q '^11\.' || sudo npm install -g --silent npm@11

# Caddy (reverse proxy + automatic HTTPS later)
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -q && sudo apt-get install -yq caddy
fi

# uv (Python toolchain; installs Python 3.12 for the project)
[ -x "$HOME/.local/bin/uv" ] || curl -LsSf https://astral.sh/uv/install.sh | sh

# code
if [ ! -d "$APP_DIR/.git" ]; then
  sudo mkdir -p "$APP_DIR" && sudo chown ubuntu:ubuntu "$APP_DIR"
  git clone "$REPO" "$APP_DIR"
fi
mkdir -p "$APP_DIR/data"

# services
sudo cp "$APP_DIR/deploy/english-tutor.service" /etc/systemd/system/english-tutor.service
sudo systemctl daemon-reload
sudo systemctl enable english-tutor >/dev/null
sudo cp "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
[ -f /etc/default/caddy ] && grep -q SITE_ADDRESS /etc/default/caddy || echo 'SITE_ADDRESS=:80' | sudo tee /etc/default/caddy >/dev/null
sudo mkdir -p /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironmentFile=/etc/default/caddy\n' | sudo tee /etc/systemd/system/caddy.service.d/env.conf >/dev/null
sudo systemctl daemon-reload
sudo systemctl restart caddy
echo "server setup done"
