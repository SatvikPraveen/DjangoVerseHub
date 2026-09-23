#!/usr/bin/env sh
# File: DjangoVerseHub/scripts/docker-entrypoint.sh
# Container entrypoint. Usage: docker-entrypoint.sh {web|asgi|worker|beat|migrate|<command...>}
set -eu

wait_for_db() {
  python - <<'PY'
import os, sys, time
import django
django.setup()
from django.db import connections
from django.db.utils import OperationalError
for attempt in range(30):
    try:
        connections["default"].cursor()
        sys.exit(0)
    except OperationalError:
        print(f"database unavailable, retrying ({attempt + 1}/30)...", flush=True)
        time.sleep(2)
sys.exit("database never became available")
PY
}

case "${1:-web}" in
  web)
    wait_for_db
    python manage.py migrate --noinput
    exec gunicorn django_verse_hub.wsgi:application \
      --bind "0.0.0.0:${PORT:-8000}" \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --access-logfile - --error-logfile -
    ;;
  asgi)
    wait_for_db
    python manage.py migrate --noinput
    exec daphne -b 0.0.0.0 -p "${PORT:-8000}" django_verse_hub.asgi:application
    ;;
  worker)
    wait_for_db
    exec celery -A django_verse_hub worker -l "${CELERY_LOG_LEVEL:-info}" \
      -Q "${CELERY_QUEUES:-celery,notifications,articles,users}" \
      --concurrency "${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    wait_for_db
    exec celery -A django_verse_hub beat -l "${CELERY_LOG_LEVEL:-info}" \
      --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;
  migrate)
    wait_for_db
    exec python manage.py migrate --noinput
    ;;
  *)
    exec "$@"
    ;;
esac
