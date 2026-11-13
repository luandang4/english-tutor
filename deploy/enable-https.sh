#!/usr/bin/env bash
# After the domain's DNS A record points at the Elastic IP: deploy/enable-https.sh tutor.example.com
# Caddy then gets a Let's Encrypt certificate; cookies become Secure; the domain is the allowed origin.
set -euo pipefail
DOMAIN=${1:?usage: deploy/enable-https.sh <domain>}
cd "$(dirname "$0")/.."
source deploy/config.sh
IP=$(public_ip)
ssh -i "$KEY_FILE" "ubuntu@$IP" "bash -s" <<REMOTE
set -euo pipefail
echo 'SITE_ADDRESS=$DOMAIN' | sudo tee /etc/default/caddy >/dev/null
sudo systemctl restart caddy
cd $APP_DIR
sed -i -E '/^(COOKIE_SECURE|ALLOWED_ORIGINS)=/d' .env
printf 'COOKIE_SECURE=true\nALLOWED_ORIGINS=["https://$DOMAIN"]\n' >> .env
sudo systemctl restart english-tutor
REMOTE
sleep 5
curl -fsS "https://$DOMAIN/api/health" && echo " <- https://$DOMAIN"
