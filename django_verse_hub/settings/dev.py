# File: DjangoVerseHub/django_verse_hub/settings/dev.py

import os

from .base import *

# Debug settings
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Development apps
# daphne first so `runserver` serves ASGI (WebSockets) in development
INSTALLED_APPS = ["daphne", *INSTALLED_APPS]
INSTALLED_APPS += [
    "debug_toolbar",
    "django_extensions",
]

MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

# Internal IPs for debug toolbar
INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]

# Debug toolbar configuration
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
    "SHOW_COLLAPSED": True,
}

# Database configuration for development
DATABASES["default"].update(
    {"OPTIONS": {"connect_timeout": 10, "options": "-c default_transaction_isolation=serializable"}}
)

# Cache: Redis when REDIS_URL is set, otherwise local memory so the project runs without Redis
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "djangoversehub_dev",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "djangoversehub-dev"}}

# Celery configuration for development
# Without Redis, run tasks inline so signup emails, notifications etc. still work
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=not REDIS_URL, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/2")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/3")

# Email configuration for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True

# Logging: readable console output plus a rotating file under logs/
LOGGING["handlers"]["file"] = {
    "class": "logging.handlers.RotatingFileHandler",
    "filename": BASE_DIR / "logs" / "django.log",
    "maxBytes": 1024 * 1024 * 10,
    "backupCount": 5,
    "formatter": "verbose",
    "filters": ["request_id"],
}
for _name in ("django_verse_hub", "apps"):
    LOGGING["loggers"][_name]["handlers"] = ["console", "file"]
    LOGGING["loggers"][_name]["level"] = "DEBUG"
LOGGING["loggers"]["django.db.backends"] = {
    "handlers": ["console"],
    "level": config("SQL_LOG_LEVEL", default="INFO"),
    "propagate": False,
}

# Ensure logs directory exists
os.makedirs(BASE_DIR / "logs", exist_ok=True)

# Development-specific settings
SHELL_PLUS_PRINT_SQL = True
SHELL_PLUS_PRE_IMPORTS = [
    ("django.contrib.auth", "get_user_model"),
    ("django.utils", "timezone"),
    ("apps.users.models", "*"),
    ("apps.articles.models", "*"),
    ("apps.comments.models", "*"),
    ("apps.notifications.models", "*"),
]

# File upload settings for development
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100MB for development
