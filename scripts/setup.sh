#!/usr/bin/env bash
# One-command install: build the branded image, start PostgreSQL, initialise the
# database (first run only), start the platform behind the HTTPS proxy and provision
# tenant, devices, alarm rules and dashboard.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  {
    echo "POSTGRES_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')"
    printf 'TB_VERSION=4.3.1.6\nTB_HTTP_PORT=8080\nTB_MQTT_PORT=1883\n'
    printf 'DOMAIN=%s\nTLS_MODE=%s\nACME_EMAIL=%s\n' "${DOMAIN:-localhost}" "${TLS_MODE:-local}" "${ACME_EMAIL:-}"
  } > .env
  chmod 600 .env
  echo "✓ Generated .env"
fi
set -a; . ./.env; set +a

if [ "${TLS_MODE}" = "local" ] && [ ! -f proxy/certs/server.crt ]; then
  ./scripts/gen-local-certs.sh "${DOMAIN}"
fi
mkdir -p proxy/certs

docker compose build thingsboard
docker compose up -d postgres
if ! docker compose exec -T postgres psql -U postgres -d thingsboard -tAc "select 1 from tb_user limit 1" 2>/dev/null | grep -q 1; then
  echo "Initialising database (first run, ~2 min)..."
  docker compose run --rm --no-deps -e INSTALL_TB=true -e LOAD_DEMO=false thingsboard
fi
docker compose up -d

echo -n "Waiting for the platform"
until [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${TB_HTTP_PORT}/login")" = 200 ]; do echo -n .; sleep 5; done
echo " up"

python3 scripts/provision.py --url "http://127.0.0.1:${TB_HTTP_PORT}" --public-url "https://${DOMAIN}" "$@"
