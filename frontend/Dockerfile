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
# build arguments, not runtime environment. Changing the public API URL means
# rebuilding this image -- there is no way around that short of shipping the
# value in a served file and reading it at boot.
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED=false
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED=$NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED

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
