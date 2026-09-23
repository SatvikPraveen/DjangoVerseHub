# File: DjangoVerseHub/Dockerfile
# syntax=docker/dockerfile:1.7
#
# Multi-stage build:
#   base        - runtime image with system libs and a non-root user
#   builder     - compiles wheels for all Python dependencies
#   development - hot reload, dev requirements, source mounted at runtime
#   production  - slim image running gunicorn (HTTP) or daphne (ASGI)

ARG PYTHON_VERSION=3.12

# --------------------------------------------------------------------------- #
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# --------------------------------------------------------------------------- #
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels -r requirements/prod.txt

# --------------------------------------------------------------------------- #
FROM base AS development

ENV DJANGO_SETTINGS_MODULE=django_verse_hub.settings.dev

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements/dev.txt

COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --------------------------------------------------------------------------- #
FROM base AS production

ENV DJANGO_SETTINGS_MODULE=django_verse_hub.settings.prod \
    GUNICORN_WORKERS=3 \
    GUNICORN_TIMEOUT=60 \
    PORT=8000

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/* && rm -rf /wheels

COPY --chown=app:app . .
RUN mkdir -p /app/staticfiles /app/media /var/log/djangoversehub \
    && chown -R app:app /app /var/log/djangoversehub

USER app

# Collect static with a throwaway secret; real settings come from the environment at runtime.
RUN SECRET_KEY=build-only ALLOWED_HOSTS=localhost REDIS_URL=redis://localhost:6379/0 \
    CELERY_BROKER_URL=redis://localhost:6379/2 CELERY_RESULT_BACKEND=redis://localhost:6379/3 \
    python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health/live/ || exit 1

COPY --chown=app:app scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["web"]
