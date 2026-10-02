#!/usr/bin/env bash
#
# Deploy whatever is checked out right now.
#
#   ./scripts/deploy.sh           # build, migrate, restart
#   ./scripts/deploy.sh --seed    # and run the seed script afterwards
#
# Deliberately does not pull. Which commit goes live is a decision, and a
# script that quietly fetches one takes it away from you:
#
#   git fetch origin && git log --oneline HEAD..origin/main   # look first
#   git merge --ff-only origin/main
#   ./scripts/deploy.sh
#
# Migrations run before the new containers start, which is the ordering that
# works for the kind of change this project makes (add a table, add a nullable
# column). A migration that drops or renames something needs the two-step
# dance instead -- deploy code that tolerates both shapes, then migrate.
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)

run_seed=false
if [[ "${1:-}" == "--seed" ]]; then
    run_seed=true
fi

if [[ ! -f .env.prod ]]; then
    echo "No infra/.env.prod. Copy .env.prod.example and fill it in." >&2
    exit 1
fi

echo "==> Building images"
"${COMPOSE[@]}" build

echo "==> Migrating the database"
# A one-off container on the new image, so the migration that runs is the one
# that shipped with this code. Postgres has to be up for it; everything else
# can still be serving the old version while this happens.
"${COMPOSE[@]}" up -d postgres
"${COMPOSE[@]}" run --rm backend alembic upgrade head

if [[ "${run_seed}" == true ]]; then
    echo "==> Seeding"
    # -e NAME with no value hands the container this shell's value. Without
    # it `compose run` passes only the service's own environment, and the
    # seed would never see the passwords the runbook says to set -- it now
    # refuses to run in production without them.
    "${COMPOSE[@]}" run --rm -e SEED_ADMIN_PASSWORD -e SEED_INSTRUCTOR_PASSWORD backend python -m scripts.seed
fi

echo "==> Starting"
"${COMPOSE[@]}" up -d --remove-orphans

echo "==> Waiting for health"
# `docker compose ps` reports the health check's own verdict, so this asks the
# same question the restart policy does rather than guessing with a sleep.
deadline=$((SECONDS + 180))
while :; do
    unhealthy="$("${COMPOSE[@]}" ps --format '{{.Service}} {{.Health}}' \
        | awk '$2 != "healthy" && $2 != "" { print $1 }')"

    if [[ -z "${unhealthy}" ]]; then
        break
    fi

    if (( SECONDS > deadline )); then
        echo "Still not healthy after 3 minutes: ${unhealthy}" >&2
        "${COMPOSE[@]}" ps >&2
        exit 1
    fi

    sleep 5
done

echo "==> Cleaning up images the new build replaced"
docker image prune -f >/dev/null

"${COMPOSE[@]}" ps
echo
echo "Deployed. Logs: docker compose -f docker-compose.prod.yml --env-file .env.prod logs -t --since 1h"

# A reminder, not a gate: the site runs fine without the monitor, it just
# breaks without anybody hearing about it.
if command -v systemctl >/dev/null && ! systemctl is-active --quiet devpath-monitor.timer; then
    echo
    echo "The host monitor is not running: sudo ./scripts/install-monitor.sh" \
        "(docs/huong-dan-deploy-vps.md, mục 4b)."
fi
