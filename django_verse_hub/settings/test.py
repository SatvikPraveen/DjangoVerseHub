# File: DjangoVerseHub/django_verse_hub/settings/test.py
"""
Test settings for DjangoVerseHub.
Optimised for fast, isolated test execution.
Set via: DJANGO_SETTINGS_MODULE=django_verse_hub.settings.test
         or pyproject.toml / pytest.ini: django_settings_module = ...
"""

from .base import *  # noqa: F401, F403
import tempfile

# ---------------------------------------------------------------------------
# Database — fast in-memory SQLite
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'timeout': 20,
        },
    }
}

# ---------------------------------------------------------------------------
# Disable migrations for faster setup
# ---------------------------------------------------------------------------
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# ---------------------------------------------------------------------------
# Email — captured in memory, never actually sent
# ---------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# ---------------------------------------------------------------------------
# Cache — local memory, no Redis required
# ---------------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

# ---------------------------------------------------------------------------
# Media / static roots
# ---------------------------------------------------------------------------
MEDIA_ROOT = tempfile.mkdtemp()
STATIC_ROOT = tempfile.mkdtemp()

# ---------------------------------------------------------------------------
# Password hashing — fastest available for tests
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# ---------------------------------------------------------------------------
# Celery — execute tasks synchronously (no broker needed)
# ---------------------------------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

# ---------------------------------------------------------------------------
# Channels — use in-memory channel layer
# ---------------------------------------------------------------------------
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# ---------------------------------------------------------------------------
# Security (relaxed — test environment only)
# ---------------------------------------------------------------------------
SECRET_KEY = 'test-secret-key-not-for-production-do-not-use'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# ---------------------------------------------------------------------------
# DRF — disable throttling in tests
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    **globals().get('REST_FRAMEWORK', {}),
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {},
}

# ---------------------------------------------------------------------------
# Logging — suppress all except critical errors
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {'class': 'logging.NullHandler'},
    },
    'root': {
        'handlers': ['null'],
        'level': 'CRITICAL',
    },
}

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024  # 1 MB
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
USE_I18N = True
USE_TZ = True
TIME_ZONE = 'UTC'
