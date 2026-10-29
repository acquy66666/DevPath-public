#!/usr/bin/env bash
# Visual regression suite (e2e/visual), run inside Playwright's Linux image.
#
#   bash scripts/visual.sh                      # compare against the baselines
#   bash scripts/visual.sh --update-snapshots   # redraw them (review the PNGs!)
#
# Needs a compose stack that is up and seeded with `scripts.seed` only -- the
# state CI's E2E job is in. A developer's everyday database has sales and
# study history the baselines do not show; bring up a clean one beside it:
#
#   cd infra && docker compose stop
#   docker compose -p devpath-visual up -d --build --wait
#   docker compose -p devpath-visual exec -T backend alembic upgrade head
#   docker compose -p devpath-visual exec -T backend python -m scripts.seed
#   COMPOSE_PROJECT=devpath-visual bash ../frontend/scripts/visual.sh
#
# The container joins the stack's network; e2e/visual/forward.mjs makes the
# services answer on localhost:3000/8000/9000 inside it, where the pages and
# the stored media URLs expect them.
set -euo pipefail

cd "$(dirname "$0")/.."
FRONTEND="$(pwd -W 2>/dev/null || pwd)"
PROJECT="${COMPOSE_PROJECT:-devpath}"
VERSION="$(node -p "require('@playwright/test/package.json').version")"
IMAGE="mcr.microsoft.com/playwright:v${VERSION}-noble"

USER_FLAG=()
if [ "$(uname -s)" = "Linux" ]; then
  # Files written into the bind mount (baselines, report) stay the runner's.
  USER_FLAG=(--user "$(id -u):$(id -g)")
fi

# Each run signs in three accounts once per project, and sign-in allows 10
# tries per email per 15 minutes: a few runs back to back would lock them out.
# Forget the count for exactly those three, nobody else's.
for email in admin@devpath.example khoa.tran@devpath.example visual-hocvien@e2e.devpath.example; do
  docker exec "${PROJECT}-redis-1" redis-cli DEL "auth:login:email:${email}" >/dev/null
done

MSYS_NO_PATHCONV=1 docker run --rm --init "${USER_FLAG[@]}" \
  --network "${PROJECT}_default" \
  -v "${FRONTEND}:/work" -w /work \
  -e HOME=/tmp -e CI="${CI:-}" -e PLAYWRIGHT_HTML_OPEN=never \
  "$IMAGE" \
  sh -c 'node e2e/visual/forward.mjs & sleep 1; exec npx playwright test --project=visual-desktop --project=visual-mobile "$@"' \
  visual "$@"
