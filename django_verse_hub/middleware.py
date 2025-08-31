# File: DjangoVerseHub/django_verse_hub/middleware.py

import time
import logging
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware to log request details and performance"""
    
    def process_request(self, request):
        request._start_time = time.time()
        
    def process_response(self, request, response):
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            logger.info(
                f'{request.method} {request.path} - '
                f'{response.status_code} - {duration:.2f}s'
            )
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Simple rate limiting middleware using Redis cache"""
    
    def process_request(self, request):
        if settings.DEBUG:
            return None
            
        # Skip rate limiting for certain paths
        skip_paths = ['/admin/', '/static/', '/media/', '/health/']
        if any(request.path.startswith(path) for path in skip_paths):
            return None
            
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        # Rate limit: 100 requests per minute
        cache_key = f'rate_limit:{ip}'
        requests = cache.get(cache_key, 0)
        
        if requests >= 100:
            return HttpResponse('Rate limit exceeded', status=429)
            
        cache.set(cache_key, requests + 1, 60)  # 60 seconds
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to responses"""
    
    def process_response(self, request, response):
        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss:;"
        )
        
        # Additional security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response