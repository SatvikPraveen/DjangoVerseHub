# File: DjangoVerseHub/django_verse_hub/settings/ci.py
"""
CI settings: identical to the test settings but backed by a real PostgreSQL
database and Redis, with migrations enabled, so the suite exercises the
production database engine, full-text search and migration graph.
"""

from decouple import config

from .test import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='djangoversehub'),
        'USER': config('DB_USER', default='django_user'),
        'PASSWORD': config('DB_PASSWORD', default='django_password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'TEST': {'NAME': 'test_djangoversehub'},
    }
}

# Run real migrations in CI so migration drift is caught.
MIGRATION_MODULES = {}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/9'),
        'KEY_PREFIX': 'djangoversehub_ci',
    }
}
