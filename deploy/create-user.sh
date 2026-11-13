#!/usr/bin/env bash
# Create an account on the server (use this once web sign-up is closed).
# Usage: deploy/create-user.sh you@example.com "Your name"   — the password is asked interactively.
set -euo pipefail
EMAIL=${1:?usage: deploy/create-user.sh EMAIL "Display name"}
NAME=${2:?usage: deploy/create-user.sh EMAIL "Display name"}
cd "$(dirname "$0")/.."
source deploy/config.sh
ssh -t -i "$KEY_FILE" "ubuntu@$(public_ip)" \
  "cd $APP_DIR/backend && ~/.local/bin/uv run -q --no-dev python scripts/create_user.py $(printf '%q' "$EMAIL") $(printf '%q' "$NAME")"
