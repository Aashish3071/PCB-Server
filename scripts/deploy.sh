#!/usr/bin/env bash
# Deploy ClimaTrack to a fresh Ubuntu/Debian cloud server over SSH, with a Let's Encrypt certificate.
#
#   ./scripts/deploy.sh <user@server-ip> <email-for-letsencrypt> [domain]
#
# Without a domain, <ip-with-dashes>.sslip.io is used (free wildcard DNS that resolves to the IP).
# The server needs ports 22, 80, 443 and 8883 open in its firewall / security group.
# Generated logins are copied back to credentials.cloud.json.
set -euo pipefail
[ $# -ge 2 ] || { sed -n '2,9p' "$0"; exit 1; }
TARGET="$1"; EMAIL="$2"; HOST="${TARGET#*@}"
DOMAIN="${3:-$(echo "$HOST" | tr . -).sslip.io}"
cd "$(dirname "$0")/.."

echo "Deploying to ${TARGET} as https://${DOMAIN}"
# Docker via the official convenience script (https://get.docker.com) if missing.
ssh "$TARGET" 'command -v docker >/dev/null || (curl -fsSL https://get.docker.com | sudo sh); sudo usermod -aG docker "$USER"'
rsync -az --delete \
  --exclude .env --exclude 'credentials*.json' --exclude 'proxy/certs/' --exclude .git \
  ./ "$TARGET":climatrack/
ssh "$TARGET" "cd climatrack && DOMAIN='$DOMAIN' TLS_MODE=acme ACME_EMAIL='$EMAIL' sg docker -c ./scripts/setup.sh"
scp -q "$TARGET":climatrack/credentials.json ./credentials.cloud.json
chmod 600 ./credentials.cloud.json
echo
echo "✓ https://${DOMAIN}  (logins: credentials.cloud.json)"
echo "  Test devices from here: python3 scripts/simulate.py --credentials credentials.cloud.json --secure"
