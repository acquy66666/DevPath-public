# Two images out of one file, picked with `target:` in compose.
#
#   development  source is bind-mounted, `next dev` reloads on change
#   production   `next build` once, then a standalone server with no toolchain
#
# Debian rather than Alpine: Next ships prebuilt native binaries and the glibc
# ones are the well-trodden path.
#
# `production` is the last stage on purpose -- a build that forgets to name a
# target gets the safe one rather than a dev server.

FROM node:22-bookworm-slim AS base
WORKDIR /app


# Lockfile-only layer: `npm ci` reruns only when dependencies actually change.
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci


FROM deps AS development
ENV NODE_ENV=development
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]


FROM deps AS build
ENV NODE_ENV=production

# NEXT_PUBLIC_* are inlined into the client bundle by `next build`, so they are
# build arguments, not runtime environment: changing one means rebuilding this
# image, with no way around it short of shipping the value in a served file and
# reading it at boot.
#
# Which is why the API URL defaults to empty, meaning "same origin as the
# page". Behind nginx that is true by construction -- /api goes to the backend
# on the very host the page was served from -- so the image carries no domain
# and the same build runs on a tunnel URL, a real domain, or an IP. Set it only
# for a deployment where the API lives somewhere else.
ARG NEXT_PUBLIC_API_BASE_URL=
ARG NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED=false

# The site's own address cannot be left to the page's origin the same way: it
# is metadataBase in app/layout.tsx, which turns every relative canonical and
# Open Graph URL into the absolute one a crawler or a chat app reads out of
# <head>. Only server code reads it, so the browser bundle still names no
# domain -- but the server bundle does, and deploy.sh rebuilds on every run, so
# a new DOMAIN takes effect on the next deploy. No default, and no building
# without it: the fallback in layout.tsx is localhost, and an image that falls
# back to it advertises http://localhost:3000 on every page it serves.
ARG NEXT_PUBLIC_SITE_URL=
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED=$NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
RUN case "$NEXT_PUBLIC_SITE_URL" in \
      http://?*|https://?*) ;; \
      *) echo "NEXT_PUBLIC_SITE_URL must be the site's absolute address (https://<domain>), got '$NEXT_PUBLIC_SITE_URL'. docker-compose.prod.yml passes it from DOMAIN." >&2; exit 1 ;; \
    esac

COPY . .
RUN npm run build


FROM base AS production
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# `output: "standalone"` in next.config.ts writes a server plus exactly the
# node_modules it traced as reachable -- a fraction of the install, and no npm
# or build toolchain left in the running image.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

# The image ships a `node` user; running as root inside a container that faces
# the internet buys nothing.
USER node

EXPOSE 3000

CMD ["node", "server.js"]
