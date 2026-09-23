# File: DjangoVerseHub/django_verse_hub/metrics.py
"""
Prometheus exposition endpoint and application-level metrics.

django-prometheus provides request/response/database metrics through its
middleware; the counters here track domain events (signups, articles
published, comments, notifications) so dashboards can show product activity
next to latency.
"""

import hmac

from django_prometheus.exports import ExportToDjangoView
from prometheus_client import Counter, Gauge

from django.conf import settings
from django.http import HttpResponseForbidden
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

users_registered_total = Counter("djangoversehub_users_registered_total", "Users who completed signup")
articles_published_total = Counter("djangoversehub_articles_published_total", "Articles that became published")
comments_created_total = Counter("djangoversehub_comments_created_total", "Comments created")
notifications_created_total = Counter(
    "djangoversehub_notifications_created_total", "Notifications created", ["notification_type"]
)
websocket_connections = Gauge("djangoversehub_websocket_connections", "Open notification WebSocket connections")


def _authorised(request):
    token = getattr(settings, "METRICS_TOKEN", "")
    if token:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        return header.startswith("Bearer ") and hmac.compare_digest(header[7:], token)
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_staff)


@require_GET
@never_cache
def metrics_view(request):
    """Prometheus text exposition; protected by METRICS_TOKEN or a staff session."""
    if not _authorised(request):
        return HttpResponseForbidden("metrics: forbidden")
    return ExportToDjangoView(request)
