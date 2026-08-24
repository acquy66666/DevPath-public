# Two images out of one file, picked with `target:` in compose.
#
#   development  source is bind-mounted, uvicorn reloads, dev extras installed
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
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies install in their own layer so editing source does not reinstall
# them. The empty app package exists only to satisfy the editable install --
# `COPY . .` further down replaces it with the real one, and the .pth file
# written into site-packages keeps pointing at /app either way.
COPY pyproject.toml README.md ./
RUN mkdir -p app && touch app/__init__.py


FROM base AS development
RUN pip install -e ".[dev]"
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


FROM base AS production
# No dev extras: pytest and ruff have no business in a running server, and
# every package that is not installed is a package that cannot be exploited.
RUN pip install -e "."
COPY . .

# Alembic and the seed script run from this image too (`docker compose run`),
# so the whole source tree stays -- not just the app package.
RUN useradd --create-home --uid 10001 devpath && chown -R devpath:devpath /app
USER devpath

EXPOSE 8000

# Workers are set by compose; this default keeps a bare `docker run` sensible.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
