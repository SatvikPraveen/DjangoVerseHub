# File: DjangoVerseHub/django_verse_hub/middleware.py

import contextlib
import contextvars
import logging
import time
import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# Current request id, readable from anywhere (logging filter, Celery task enqueue, ...)
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_ID_HEADER = "X-Request-ID"


def get_request_id():
    return request_id_var.get()


class RequestIDFilter(logging.Filter):
    """Inject the current request id into every log record."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


class RequestIDMiddleware(MiddlewareMixin):
    """
    Accept an upstream X-Request-ID (from nginx / a load balancer) or mint one,
    expose it as request.id, echo it in the response and make it available to logs.
    """

    def process_request(self, request):
        incoming = request.META.get(REQUEST_ID_HEADER, "").strip()
        request_id = incoming[:64] if incoming and incoming.isascii() else uuid.uuid4().hex
        request.id = request_id
        request._request_id_token = request_id_var.set(request_id)

    def process_response(self, request, response):
        request_id = getattr(request, "id", None)
        if request_id:
            response[RESPONSE_ID_HEADER] = request_id
        token = getattr(request, "_request_id_token", None)
        if token is not None:
            with contextlib.suppress(ValueError):
                request_id_var.reset(token)
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """Log one structured line per request with timing and identity."""

    SKIP_PREFIXES = ("/static/", "/media/", "/health/", "/metrics/", "/__debug__/")

    def process_request(self, request):
        request._start_time = time.perf_counter()

    def process_response(self, request, response):
        if request.path.startswith(self.SKIP_PREFIXES) or not hasattr(request, "_start_time"):
            return response
        duration_ms = (time.perf_counter() - request._start_time) * 1000
        user = getattr(request, "user", None)
        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
            extra={
                "http_method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
                "user_id": str(user.pk) if user is not None and user.is_authenticated else None,
                "ip": _client_ip(request),
            },
        )
        slow_threshold = getattr(settings, "SLOW_REQUEST_THRESHOLD_MS", 1000)
        if duration_ms > slow_threshold:
            logger.warning("slow request %s %s took %.0fms", request.method, request.path, duration_ms)
        return response


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class RateLimitMiddleware(MiddlewareMixin):
    """Simple rate limiting middleware using Redis cache"""

    def process_request(self, request):
        if settings.DEBUG or not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return None

        # Skip rate limiting for certain paths
        skip_paths = ["/admin/", "/static/", "/media/", "/health/", "/metrics/"]
        if any(request.path.startswith(path) for path in skip_paths):
            return None

        ip = _client_ip(request)

        limit = getattr(settings, "RATE_LIMIT_REQUESTS_PER_MINUTE", 100)
        cache_key = f"rate_limit:{ip}"
        requests = cache.get(cache_key, 0)

        if requests >= limit:
            response = HttpResponse("Rate limit exceeded", status=429)
            response["Retry-After"] = "60"
            return response

        cache.set(cache_key, requests + 1, 60)  # 60 seconds
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Content-Security-Policy and related headers, built from settings so a
    deployment can add CDNs or analytics hosts without code changes.
    """

    def build_csp(self):
        cdn = ["https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"]
        extra = getattr(settings, "CSP_EXTRA_SOURCES", {})
        directives = {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", *cdn, *extra.get("script-src", [])],
            "style-src": [
                "'self'",
                "'unsafe-inline'",
                *cdn,
                "https://fonts.googleapis.com",
                *extra.get("style-src", []),
            ],
            "font-src": ["'self'", "data:", *cdn, "https://fonts.gstatic.com", *extra.get("font-src", [])],
            "img-src": ["'self'", "data:", "blob:", "https:", *extra.get("img-src", [])],
            "connect-src": ["'self'", "ws:", "wss:", *extra.get("connect-src", [])],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'", *extra.get("form-action", [])],
            "object-src": ["'none'"],
        }
        parts = [f"{name} {' '.join(values)}" for name, values in directives.items()]
        if getattr(settings, "CSP_REPORT_URI", ""):
            parts.append(f"report-uri {settings.CSP_REPORT_URI}")
        return "; ".join(parts)

    def process_response(self, request, response):
        if getattr(settings, "CSP_ENABLED", True) and "Content-Security-Policy" not in response:
            header = (
                "Content-Security-Policy-Report-Only"
                if getattr(settings, "CSP_REPORT_ONLY", False)
                else "Content-Security-Policy"
            )
            response[header] = self.build_csp()

        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
        )
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response
