#!/usr/bin/env bash
# Change one setting in the server's .env and restart the app.
# Usage: deploy/set-env.sh ALLOW_REGISTRATION=false
set -euo pipefail
PAIR=${1:?usage: deploy/set-env.sh KEY=VALUE}
KEY=${PAIR%%=*}
[[ "$KEY" =~ ^[A-Z0-9_]+$ ]] || { echo "invalid key: $KEY" >&2; exit 1; }
cd "$(dirname "$0")/.."
source deploy/config.sh
printf '%s\n' "$PAIR" | ssh -i "$KEY_FILE" "ubuntu@$(public_ip)" \
  "cd $APP_DIR && sed -i -E '/^$KEY=/d' .env && cat >> .env && sudo systemctl restart english-tutor && echo '$KEY updated, app restarted'"
