#!/usr/bin/env bash
#
# Put the running production stack on a public HTTPS URL.
#
#   ./scripts/tunnel.sh          # start it, print the URL
#   ./scripts/tunnel.sh --url    # print the URL of the one already running
#   ./scripts/tunnel.sh --stop   # stop it
#
# Needs the production stack up first (./scripts/deploy.sh). The URL is random,
# changes on every restart, and lives only as long as this machine does -- see
# the header of docker-compose.tunnel.yml for what a quick tunnel is and is not.
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(
    docker compose
    -f docker-compose.prod.yml
    -f docker-compose.tunnel.yml
    --env-file .env.prod
)

if [[ ! -f .env.prod ]]; then
    echo "No infra/.env.prod. Copy .env.prod.example and fill it in." >&2
    exit 1
fi

# cloudflared announces the hostname once, in a banner, and never again. So the
# log is the only place it exists -- read from the beginning of the container's
# life, not the tail, or a tunnel that has been up a while has nothing to show.
print_url() {
    local deadline=$((SECONDS + 60)) url=""

    while :; do
        url="$("${COMPOSE[@]}" logs cloudflared 2>&1 \
            | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' \
            | tail -1 || true)"

        if [[ -n "${url}" ]]; then
            break
        fi

        if (( SECONDS > deadline )); then
            echo "cloudflared has not printed a URL in 60s. Its log:" >&2
            "${COMPOSE[@]}" logs --tail 30 cloudflared >&2
            return 1
        fi

        sleep 2
    done

    echo
    echo "  ${url}"
    echo
    echo "  Random, and a different one after every restart of this container."
    echo "  Alive only while this machine is on. Sign in with a password:"
    echo "  Google needs a redirect URI registered in advance, which rules out"
    echo "  a URL nobody knows in advance."
    echo
}

case "${1:-}" in
    --stop)
        "${COMPOSE[@]}" stop cloudflared
        echo "Tunnel stopped. The stack itself is still running."
        exit 0
        ;;
    --url)
        print_url
        exit 0
        ;;
    "") ;;
    *)
        echo "Usage: $0 [--url | --stop]" >&2
        exit 1
        ;;
esac

# `ps -q` on a service that is not up prints nothing, which is the check --
# without nginx there is nothing to put on the internet, and cloudflared would
# sit there retrying an origin that never answers.
if [[ -z "$("${COMPOSE[@]}" ps -q nginx)" ]]; then
    echo "The production stack is not running. Start it first:" >&2
    echo "  ./scripts/deploy.sh" >&2
    exit 1
fi

echo "==> Starting the tunnel"
"${COMPOSE[@]}" up -d cloudflared

print_url
