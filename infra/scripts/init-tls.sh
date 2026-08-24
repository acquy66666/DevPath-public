#!/usr/bin/env bash
#
# First certificate for a brand-new VPS. Run once, before the first deploy.
#
#   ./scripts/init-tls.sh              # real certificate
#   ./scripts/init-tls.sh --staging    # Let's Encrypt's test CA, no rate limit
#
# The chicken-and-egg this exists to break: nginx refuses to start when the
# certificate file in its config does not exist, and certbot cannot answer the
# HTTP challenge unless something is already serving port 80. So a throwaway
# self-signed certificate goes in first, nginx comes up on it, certbot replaces
# it with the real one, and nginx reloads.
#
# Before running: the domain's A record must already point at this machine, and
# ports 80 and 443 must be open. The challenge is an inbound HTTP request from
# Let's Encrypt; nothing else in this script can make that work.
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)

staging_flag=""
if [[ "${1:-}" == "--staging" ]]; then
    staging_flag="--staging"
    echo "==> Staging CA: the certificate will not be trusted by browsers."
fi

# Export everything the file sets, so DOMAIN and ACME_EMAIL below come from it.
set -a
# shellcheck disable=SC1091  # .env.prod exists on the server, not in the repo.
source .env.prod
set +a

: "${DOMAIN:?set DOMAIN in .env.prod}"
: "${ACME_EMAIL:?set ACME_EMAIL in .env.prod}"

live_path="/etc/letsencrypt/live/${DOMAIN}"

echo "==> Placeholder certificate for ${DOMAIN}"
# Runs in the certbot image because it has openssl and the letsencrypt volume;
# nothing has to be installed on the host.
"${COMPOSE[@]}" run --rm --entrypoint sh certbot -c "
    set -e
    if [ -s '${live_path}/fullchain.pem' ]; then
        echo 'A certificate is already there, leaving it alone.'
        exit 0
    fi
    mkdir -p '${live_path}'
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout '${live_path}/privkey.pem' \
        -out '${live_path}/fullchain.pem' \
        -subj '/CN=${DOMAIN}'
"

echo "==> Starting nginx so the challenge has somewhere to land"
"${COMPOSE[@]}" up -d nginx

echo "==> Asking Let's Encrypt for the real certificate"
# --force-renewal because the placeholder above is, as far as certbot can tell,
# a perfectly good certificate that is not due for renewal yet.
"${COMPOSE[@]}" run --rm certbot certonly \
    --webroot --webroot-path /var/www/certbot \
    --email "${ACME_EMAIL}" \
    --agree-tos --no-eff-email \
    --force-renewal \
    ${staging_flag} \
    -d "${DOMAIN}"

echo "==> Reloading nginx onto the real certificate"
"${COMPOSE[@]}" exec nginx nginx -s reload

echo
echo "Done. https://${DOMAIN} should answer now."
echo "Renewal is automatic: the certbot service checks twice a day."
