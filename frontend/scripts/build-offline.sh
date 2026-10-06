#!/bin/sh
# `next build` with no network at all, to prove a build fetches nothing.
#
# next/font/google downloads its CSS and font files from Google while it
# builds, and Google sometimes answers with URLs Next cannot parse
# (vercel/next.js#99114): the build -- and every page of `next dev` -- then
# fails at random. The fonts live in public/fonts now; this is the check that
# nothing went back to fetching them.
#
# Run from the repository root with the dev stack's frontend container up:
#   docker run --rm --network none --volumes-from devpath-frontend-1 \
#     devpath-frontend:dev sh /app/scripts/build-offline.sh
#
# It copies the sources to /tmp so the dev server's .next is left alone, minus
# the Playwright suite: the dev image's node_modules has no @playwright/test,
# and the suite is not part of the app the build type-checks.
set -eu
rm -rf /tmp/offline-build
mkdir -p /tmp/offline-build
cd /app
tar cf - --exclude=./.next --exclude=./node_modules --exclude=./public/monaco \
  --exclude=./e2e --exclude=./playwright.config.ts . \
  | (cd /tmp/offline-build && tar xf -)
cp -a /app/node_modules /tmp/offline-build/node_modules
cd /tmp/offline-build
export NEXT_TELEMETRY_DISABLED=1
export NEXT_PUBLIC_SITE_URL=https://offline.devpath.example
# The dev image sets NODE_ENV=development, and `next build` under it fails to
# prerender ("Cannot read properties of null (reading 'useContext')").
export NODE_ENV=production
npx next build
