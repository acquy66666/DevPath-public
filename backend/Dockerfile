# Development image. Source is bind-mounted by compose and uvicorn reloads on
# change, so this only has to provide the interpreter and the dependencies.
FROM python:3.12-slim

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
# `COPY . .` below replaces it with the real one, and the .pth file written
# into site-packages keeps pointing at /app either way.
COPY pyproject.toml README.md ./
RUN mkdir -p app && touch app/__init__.py \
    && pip install -e ".[dev]"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
