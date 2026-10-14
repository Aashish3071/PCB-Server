#!/usr/bin/env bash
# Create a local test CA and a TLS certificate for $DOMAIN (default localhost) in proxy/certs.
# For local HTTPS testing only; the cloud deployment uses Let's Encrypt (TLS_MODE=acme).
set -euo pipefail
cd "$(dirname "$0")/../proxy"
DOMAIN="${1:-localhost}"
# Also valid for this machine's LAN addresses, so devices on the same network can use TLS.
SANS="DNS:${DOMAIN},DNS:localhost,IP:127.0.0.1"
for ip in $( (ipconfig getifaddr en0; ipconfig getifaddr en1; hostname -I) 2>/dev/null ); do SANS="${SANS},IP:${ip}"; done
mkdir -p certs && cd certs
if [ ! -f ca.crt ]; then
  printf "[req]\ndistinguished_name=dn\nx509_extensions=v3_ca\n[dn]\n[v3_ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n" > ca.cnf
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -subj "/CN=ClimaTrack Local Test CA" \
    -config ca.cnf -keyout ca.key -out ca.crt 2>/dev/null
  rm -f ca.cnf
fi
openssl req -newkey rsa:2048 -nodes -subj "/CN=${DOMAIN}" -keyout server.key -out server.csr 2>/dev/null
printf "subjectAltName=%s\nextendedKeyUsage=serverAuth\nkeyUsage=critical,digitalSignature,keyEncipherment\nbasicConstraints=CA:FALSE\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n" "$SANS" > server.ext
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 397 -extfile server.ext -out server.crt 2>/dev/null
rm -f server.csr server.ext
chmod 600 ca.key server.key
echo "✓ proxy/certs/server.crt for ${DOMAIN} (trust proxy/certs/ca.crt in test clients)"
