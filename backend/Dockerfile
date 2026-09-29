# Four images out of one file, picked with `target:` in compose.
#
#   development  source is bind-mounted, uvicorn reloads, dev extras installed
#   grading-*    the matching stage plus the Docker CLI, for the grading worker
#   runtime      shared base of the two production images
#   production   source baked in, no test tooling, no reloader
#
# `production` is the last stage on purpose -- a build that forgets to name a
# target gets the safe one rather than a reloading dev server.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg is the transcoder the Celery worker shells out to. Backend and
# worker share one image (compose builds it once), so the API container
# carries it too -- ~250 MB for one build instead of maintaining two.
#
# Pango and HarfBuzz are what WeasyPrint lays certificate text out with, and
# DejaVu is the font it lays it out in: the slim image has no fonts at all,
# and a certificate drawn without one comes out as rows of empty boxes --
# every Vietnamese name has diacritics, so "most of the text renders" is not
# a state worth shipping.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies install in their own layer so editing source does not reinstall
# them. The empty app package exists only to satisfy the editable install --
# `COPY . .` further down replaces it with the real one, and the .pth file
# written into site-packages keeps pointing at /app either way.
#
# Every install goes through requirements.lock: pyproject.toml only sets lower
# bounds, so without it an image built on the morning of the defence could hold
# a FastAPI or SQLAlchemy nobody has ever run the tests against. The lock also
# lists the dev tools; as a constraints file it pins what is installed and
# installs nothing by itself, so the production stages stay without them.
COPY pyproject.toml requirements.lock README.md ./
RUN mkdir -p app && touch app/__init__.py


FROM base AS development
RUN pip install -e ".[dev]" -c requirements.lock
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# The grading worker, and nothing else, talks to the Docker daemon: it starts
# one throwaway container per test case. The CLI is copied from Docker's own
# image rather than installed from a distribution package, which would drag in
# the whole engine -- and is pinned, because the client is how this service
# reaches a daemon it does not control.
#
# A separate stage so the API image stays free of it. A container holding the
# daemon socket can start any container it likes on the host, so the number of
# images able to do that should be one.
FROM development AS grading-development
COPY --from=docker:29-cli /usr/local/bin/docker /usr/local/bin/docker
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "grading"]


FROM base AS runtime
# No dev extras: pytest and ruff have no business in a running server, and
# every package that is not installed is a package that cannot be exploited.
RUN pip install -e "." -c requirements.lock
COPY . .

# Alembic and the seed script run from this image too (`docker compose run`),
# so the whole source tree stays -- not just the app package.
RUN useradd --create-home --uid 10001 devpath && chown -R devpath:devpath /app
USER devpath


# The production grading worker. Same CLI, same reason -- and it stays uid
# 10001, so on the VPS the container has to be put in the host's docker group
# (`group_add` in docker-compose.prod.yml) to reach the socket at all. Running
# it as root instead would be one less line and a much larger hole.
FROM runtime AS grading-production
COPY --from=docker:29-cli /usr/local/bin/docker /usr/local/bin/docker
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "grading"]


# Last on purpose: see the header. Everything it needs is in `runtime`; this
# stage exists to be the default, and to be the one without a Docker client.
FROM runtime AS production
EXPOSE 8000

# Workers are set by compose; this default keeps a bare `docker run` sensible.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
