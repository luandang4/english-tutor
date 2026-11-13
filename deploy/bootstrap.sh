#!/usr/bin/env bash
# First-time server setup after provision.sh: system packages, .env, first release.
# The local .env (API keys) is copied over SSH; production overrides are appended. Nothing is printed.
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh
IP=$(public_ip)
SSH=(ssh -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new "ubuntu@$IP")

"${SSH[@]}" 'bash -s' < deploy/server-setup.sh

# .env: local keys + production settings (later keys win, overridden ones are dropped first)
OVERRIDES="TTS_STORAGE=s3
TTS_S3_BUCKET=$BUCKET
TTS_PREFETCH=true
COOKIE_SECURE=false
API_DOCS=false
ALLOWED_ORIGINS=[\"http://$IP\"]"
{ grep -vE '^(TTS_STORAGE|TTS_S3_BUCKET|TTS_PREFETCH|COOKIE_SECURE|API_DOCS|ALLOWED_ORIGINS|DATABASE_URL)=' .env; echo "$OVERRIDES"; } \
  | "${SSH[@]}" "umask 077 && cat > $APP_DIR/.env"

deploy/deploy.sh
