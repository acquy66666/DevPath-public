# Development image. Source is bind-mounted by compose and Next.js reloads on
# change. Debian rather than Alpine: Next ships prebuilt native binaries and
# the glibc ones are the well-trodden path.
FROM node:22-bookworm-slim

ENV NODE_ENV=development

WORKDIR /app

# Lockfile-only layer: `npm ci` reruns only when dependencies actually change.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
