# File: DjangoVerseHub/django_verse_hub/health.py
"""
Health endpoints for orchestrators and load balancers.

- /health/live/   liveness: the process is up and can serve a request.
- /health/ready/  readiness: every dependency the app needs is reachable.
- /health/        legacy alias for readiness.
"""

import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def _check_database():
    started = time.perf_counter()
    with connections['default'].cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.fetchone()
    return {'status': 'ok', 'latency_ms': round((time.perf_counter() - started) * 1000, 2)}


def _check_cache():
    started = time.perf_counter()
    key = 'health:ping'
    cache.set(key, '1', 5)
    if cache.get(key) != '1':
        raise RuntimeError('cache round-trip failed')
    return {'status': 'ok', 'latency_ms': round((time.perf_counter() - started) * 1000, 2)}


def _check_celery():
    """Ping the broker; skipped when tasks run eagerly (tests, local dev)."""
    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        return {'status': 'skipped', 'reason': 'eager mode'}
    started = time.perf_counter()
    from django_verse_hub.celery import app as celery_app

    with celery_app.connection_for_read() as connection:
        connection.ensure_connection(max_retries=1, interval_start=0, interval_step=0)
    return {'status': 'ok', 'latency_ms': round((time.perf_counter() - started) * 1000, 2)}


CHECKS = ('database', 'cache', 'celery')


@require_GET
@never_cache
def liveness(request):
    return JsonResponse({'status': 'ok'})


@require_GET
@never_cache
def readiness(request):
    results = {}
    healthy = True
    for name in CHECKS:
        check = globals()[f'_check_{name}']
        try:
            results[name] = check()
        except Exception as exc:  # noqa: BLE001 - any failure means "not ready"
            logger.warning('health check %s failed: %s', name, exc)
            results[name] = {'status': 'error', 'error': str(exc)[:200]}
            healthy = False

    payload = {
        'status': 'ok' if healthy else 'degraded',
        'checks': results,
        'version': getattr(settings, 'APP_VERSION', 'unknown'),
    }
    return JsonResponse(payload, status=200 if healthy else 503)
