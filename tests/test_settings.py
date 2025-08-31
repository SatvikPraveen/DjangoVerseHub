"""
File: tests/test_settings.py
Test-specific Django settings configuration.
Optimized for fast test execution and isolated testing environment.
"""

from config.settings.base import *
import tempfile
import os

# Test database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # In-memory database for faster tests
        'OPTIONS': {
            'timeout': 20,
        }
    }
}

# Disable migrations for faster test setup
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Cache configuration for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

# Media files configuration
MEDIA_ROOT = tempfile.mkdtemp()

# Static files configuration
STATIC_ROOT = tempfile.mkdtemp()

# Disable logging during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'CRITICAL',
    },
}

# Password hashers - use fast hasher for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Celery configuration for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable middleware that might interfere with tests
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

# Debug toolbar and other development tools
if 'debug_toolbar' in INSTALLED_APPS:
    INSTALLED_APPS.remove('debug_toolbar')

# Test-specific settings
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# File upload settings for tests
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024  # 1MB

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# Internationalization for tests
USE_I18N = True
USE_TZ = True
TIME_ZONE = 'UTC'

# Security settings (relaxed for tests)
SECRET_KEY = 'test-secret-key-not-for-production'
DEBUG = False
ALLOWED_HOSTS = ['testserver']

# API throttling (disabled for tests)
REST_FRAMEWORK = {
    **globals().get('REST_FRAMEWORK', {}),
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {},
}

# Disable CSRF for API tests
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False