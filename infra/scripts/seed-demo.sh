#!/usr/bin/env bash
#
# The demo data, on the production stack: the scripts the README lists for the
# four real courses (README.md, "Dữ liệu demo đầy đủ" and "Trước buổi bảo
# vệ"), in that order, then the AI side the dev machine already had.
#
#   ./scripts/seed-demo.sh            # after ./scripts/deploy.sh --seed
#
# What a demo needs that `--seed` alone does not give: lecture transcripts
# for the assistant, homepage banners, a year of sales for the dashboards,
# seventy days of study for XP, streaks and the leaderboard, the coupon codes,
# certificates, a fuller catalogue (scripts.seed_catalogue), and -- with
# GEMINI_API_KEY set -- the course material embedded
# for the assistant and the recommender. Without that last part the assistant
# answers every question with "chưa có tài liệu".
#
# Each script writes nothing the second time. The dates are relative to the
# moment they run and age (README: "dữ liệu già đi"): the day before a demo,
# run `scripts.seed_study --purge` then `scripts.seed_sales --purge` in the
# backend container, then this again.
#
# The buyer accounts seed_sales makes share one password written in the repo
# (nguoimuaNN@sales.devpath.example / devpath-buyer). Fine for a demo address;
# not for a site with real users.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env.prod ]]; then
    echo "No infra/.env.prod. Copy .env.prod.example and fill it in." >&2
    exit 1
fi

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)
# The same rule as deploy.sh: the stack was started with the overlay, so it is
# addressed with it.
if grep -Eq '^TUNNEL_TOKEN=.+' .env.prod; then
    COMPOSE=(docker compose -f docker-compose.prod.yml -f docker-compose.named-tunnel.yml
        --env-file .env.prod)
fi

if [[ -z "$("${COMPOSE[@]}" ps -q backend)" ]]; then
    echo "The production stack is not running. Start it first: ./scripts/deploy.sh --seed" >&2
    exit 1
fi

run() {
    echo "==> $*"
    "${COMPOSE[@]}" exec -T backend python -m "$@"
}

run scripts.seed_transcripts
run scripts.seed_banners
run scripts.seed_sales
run scripts.seed_study
run scripts.seed_coupons
run scripts.rebuild_leaderboard
run scripts.issue_certificates
# Twenty-two more real courses for the catalogue page. After seed_sales on
# purpose: the sales stay on the four real courses, so the dashboards read
# the same numbers as on the dev machine.
run scripts.seed_catalogue

if grep -Eq '^GEMINI_API_KEY=.+' .env.prod; then
    # Embeds every published course's material (the assistant) and each
    # course as a whole (the recommender). Re-running costs no quota: what is
    # already embedded with the same model is skipped.
    run scripts.ingest_course --all
    run scripts.rebuild_course_embeddings
else
    echo "==> GEMINI_API_KEY is empty: no assistant, and recommendations from" \
        "purchases only. Set it in .env.prod and run this again."
fi

run scripts.rebuild_recommendations

echo
echo "Demo data in place. Accounts: the admin and instructors from SEED_*_PASSWORD;" \
    "buyers nguoimua01..40@sales.devpath.example / devpath-buyer."
