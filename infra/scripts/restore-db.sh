#!/usr/bin/env bash
#
# Put the database back from a backup.
#
#   ./scripts/restore-db.sh                  # list the backups, change nothing
#   ./scripts/restore-db.sh latest           # restore the newest one
#   ./scripts/restore-db.sh postgres/devpath-20261002T190000Z.dump
#
# In three steps, so the site is down only for the middle one:
#
#   1. restore into a NEW side database, while the site keeps serving from the
#      live one, and print how the two differ table by table;
#   2. ask, then stop the services that hold connections and swap the names --
#      the restored copy becomes the live database, the old one is parked
#      under `<db>_before_restore_<time>`, not dropped;
#   3. start everything again and wait for it to be healthy.
#
# Going back is the same swap the other way round, so nothing here is final
# until you drop the parked copy yourself.
#
# Also runs on the dev stack, which is how the drill was done:
#   COMPOSE_FILE=docker-compose.yml ./scripts/restore-db.sh latest
set -euo pipefail

cd "$(dirname "$0")/.."

compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
if [[ "${compose_file}" == "docker-compose.prod.yml" ]]; then
    if [[ ! -f .env.prod ]]; then
        echo "No infra/.env.prod. Copy .env.prod.example and fill it in." >&2
        exit 1
    fi
    COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)
else
    COMPOSE=(docker compose -f "${compose_file}" --profile backup)
fi

# Everything that keeps a connection to the database open. A rename waits for
# none of them -- Postgres refuses it while anyone is connected.
APP_SERVICES=(backend worker beat grading-worker)

if [[ $# -eq 0 ]]; then
    "${COMPOSE[@]}" run --rm backup list
    exit 0
fi

echo "==> Restoring $1 into a side database (the site is still up)"
# -T and </dev/null: `compose run` attaches stdin by default -- it would swallow
# the answer to the question below -- and a pseudo-TTY would end every line
# with a carriage return, the RESTORED= line included.
output="$("${COMPOSE[@]}" run --rm -T backup restore "$1" </dev/null | tee /dev/stderr)"
restored="$(printf '%s\n' "${output}" | sed -n 's/^RESTORED=//p' | tail -n 1)"
if [[ -z "${restored}" ]]; then
    echo "The restore did not report a database name; nothing was swapped." >&2
    exit 1
fi

read -r -p "Swap ${restored} in as the live database? This stops the site briefly. [y/N] " answer
if [[ "${answer}" != "y" && "${answer}" != "Y" ]]; then
    echo "Left as it is. ${restored} stays beside the live database; drop it with:"
    # Single quotes in the printed command: POSTGRES_USER is set inside the
    # postgres container, not in the shell that pastes this.
    echo "  ${COMPOSE[*]} exec postgres sh -c 'dropdb -U \"\$POSTGRES_USER\" ${restored}'"
    exit 0
fi

echo "==> Stopping ${APP_SERVICES[*]}"
"${COMPOSE[@]}" stop "${APP_SERVICES[@]}"

echo "==> Swapping"
if ! "${COMPOSE[@]}" run --rm -T backup swap "${restored}" --yes </dev/null; then
    echo "Swap failed; starting the services again on the old database." >&2
    "${COMPOSE[@]}" up -d "${APP_SERVICES[@]}"
    exit 1
fi

echo "==> Starting ${APP_SERVICES[*]}"
"${COMPOSE[@]}" up -d "${APP_SERVICES[@]}"

echo "==> Waiting for health"
deadline=$((SECONDS + 180))
while :; do
    unhealthy="$("${COMPOSE[@]}" ps --format '{{.Service}} {{.Health}}' "${APP_SERVICES[@]}" \
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

echo "==> Done. The previous database is parked, not dropped -- see the swap line above."
