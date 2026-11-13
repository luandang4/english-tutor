#!/usr/bin/env bash
# Deploy the pushed main branch to EC2. Usage: deploy/deploy.sh   (or: make deploy)
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

git fetch -q origin main
if [ "$(git rev-parse main)" != "$(git rev-parse origin/main)" ]; then
  echo "main and origin/main differ: push first (git push origin main)." >&2
  exit 1
fi
IP=$(public_ip)
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new "ubuntu@$IP" 'bash -s' < deploy/release.sh
curl -fsS "http://$IP/api/health" && echo " <- http://$IP"
