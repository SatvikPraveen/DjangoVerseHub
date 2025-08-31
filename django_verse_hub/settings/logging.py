# File: DjangoVerseHub/django_verse_hub/settings/logging.py

import os
from decouple import config

# Base directory for logs
LOGS_DIR = config('LOGS_DIR', default='/var/log/djangoversehub/')

# Create logs directory if it doesn't exist
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'json': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s %(pathname)s %(funcName)s %(lineno)d'
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'console_prod': {
            'level': 'WARNING',
            'filters': ['require_debug_false'],
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'django_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'django.log'),
            'maxBytes': 1024*1024*10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'app_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'app.log'),
            'maxBytes': 1024*1024*10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'error.log'),
            'maxBytes': 1024*1024*10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'security.log'),
            'maxBytes': 1024*1024*10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'celery.log'),
            'maxBytes': 1024*1024*10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'formatter': 'verbose',
            'include_html': True,
        },
    },
    'root': {
        'handlers': ['console', 'console_prod'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'console_prod', 'django_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file', 'mail_admins'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['django_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django_verse_hub': {
            'handlers': ['console', 'console_prod', 'app_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'console_prod', 'app_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['celery_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.task': {
            'handlers': ['celery_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.worker': {
            'handlers': ['celery_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'channels': {
            'handlers': ['app_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'PIL': {
            'handlers': ['app_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}