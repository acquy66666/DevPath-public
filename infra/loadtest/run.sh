#!/usr/bin/env bash
#
# Load test against a running production stack (docker-compose.prod.yml).
#
#   ./loadtest/run.sh catalogue      # 10, 25, 50, 100 people browsing
#   ./loadtest/run.sh class          # a class submits at once, then again
#                                    # with people browsing at the same time
#
# k6 runs in a container on the stack's own network and talks to nginx, so
# what is measured is the server, not the path from this machine to it. The
# class is staged by a backend script and taken away again by purge_e2e, even
# when a run fails.
#
# Environment, with the VPS defaults:
#   COMPOSE_PROJECT_NAME  devpath            (devpath-prodtest on a dev machine)
#   ENV_FILE              .env.prod
#   OUT                   ../docs/report/assets/phase-6/load-test
#   LEVELS                "10 25 50 100"     catalogue: people browsing at once
#   CLASS                 20                 class: students submitting at once
#   BROWSE_VUS            25                 class: people browsing alongside
set -euo pipefail

cd "$(dirname "$0")/.."

project="${COMPOSE_PROJECT_NAME:-devpath}"
env_file="${ENV_FILE:-.env.prod}"
out="${OUT:-../docs/report/assets/phase-6/load-test}"
levels="${LEVELS:-10 25 50 100}"
class_size="${CLASS:-20}"
browse_vus="${BROWSE_VUS:-25}"
k6_image="grafana/k6:2.3.0"

COMPOSE=(docker compose -p "${project}" -f docker-compose.prod.yml --env-file "${env_file}")

# Git Bash on Windows rewrites anything that looks like a path, including the
# container side of -v; and Docker Desktop wants the Windows form of the host
# side. Both are no-ops on Linux.
export MSYS_NO_PATHCONV=1
host_path() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }

mkdir -p "${out}"
scripts="$(host_path loadtest)"
results="$(host_path "${out}")"
stage_dir="$(mktemp -d)"
trap 'rm -rf "${stage_dir}"' EXIT

k6() {
    local status=0
    docker run --rm \
        --network "${project}_default" \
        -v "${scripts}:/scripts:ro" \
        -v "${results}:/out" \
        -v "$(host_path "${stage_dir}"):/stage:ro" \
        -e BASE_URL=https://nginx \
        -e INSECURE_TLS=1 \
        "$@" \
        "${k6_image}" run --quiet "/scripts/${K6_SCRIPT}" || status=$?
    # 99 is k6 saying a threshold was crossed. That is a finding to read in
    # the numbers, not a reason to skip the levels after it.
    if [[ ${status} -eq 99 ]]; then
        echo "    (vượt ngưỡng -- xem số ở trên)"
    elif [[ ${status} -ne 0 ]]; then
        return "${status}"
    fi
}

catalogue() {
    for vus in ${levels}; do
        echo "==> Catalogue, ${vus} people browsing"
        K6_SCRIPT=catalogue.js k6 -e VUS="${vus}" -e DURATION=60s
        # Let the last requests drain so one level does not bleed into the next.
        sleep 10
    done
}

stage_class() {
    # One more than the class: the last student submits alone first.
    "${COMPOSE[@]}" exec -T backend python -m scripts.stage_load_test \
        --students "$((class_size + 1))" --cases 5 > "${stage_dir}/stage.json"
}

purge() {
    "${COMPOSE[@]}" exec -T backend python -m scripts.purge_e2e
}

class() {
    trap 'purge; rm -rf "${stage_dir}"' EXIT

    echo "==> A class of ${class_size} submits at once"
    stage_class
    K6_SCRIPT=submissions.js k6 -e STAGE=/stage/stage.json
    purge

    # The cooldown is per student, so the second run gets a fresh class.
    echo "==> The same class, with ${browse_vus} people browsing meanwhile"
    stage_class
    K6_SCRIPT=submissions.js k6 -e STAGE=/stage/stage.json -e BROWSE_VUS="${browse_vus}"
}

case "${1:-}" in
    catalogue) catalogue ;;
    class) class ;;
    *)
        echo "usage: $0 catalogue|class" >&2
        exit 2
        ;;
esac
